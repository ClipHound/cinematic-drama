# SDD-02-离线系统设计

> 版本：v1.0  
> 定稿日期：2026-06-10  
> 实现模块：`drama-understanding-agent/src/`  
> 核心依赖：Doubao VLM API (方舟), FunASR, Qdrant, Ollama (BGE-M3)

## 2.1 离线系统职责边界

离线系统负责短剧入库后的全自动内容理解与互动编排。它运行于服务端，不依赖客户端交互，可以与在线服务分离部署。

**输入**：
- 短剧视频文件（MP4，每集 2-7 分钟）
- Project 元数据（剧名、总集数）
- 可选：已有 ASR 文件

**输出**（三类产物）：
- `ep_*.interactions.json` — 每集互动清单（Manifest）
- `rhythm_blueprint.json` — 全剧节奏蓝图
- `report.json` — 理解报告（角色、关系、剧情摘要）

## 2.2 模块分解

```
drama-understanding-agent/src/
├── drama_agent/           # 核心引擎
│   ├── config.py          # 配置管理 (Pydantic Settings)
│   ├── project.py         # Project 工作空间管理
│   ├── cli.py             # 命令行入口 (typer)
│   ├── asr/               # ASR 转录
│   │   ├── client.py      # FunASR HTTP 客户端
│   │   └── sentence_merger.py  # 词→句合并
│   ├── model/             # AI 模型接口
│   │   ├── client.py      # Doubao API 客户端 (base64/File API)
│   │   ├── prompts.py     # System/Episode Prompt 模板
│   │   └── ark_utils.py   # 方舟 API URL 工具
│   ├── memory/            # 记忆系统
│   │   ├── store.py       # SQLite CRUD
│   │   ├── vectors.py     # Qdrant 向量封装
│   │   ├── embeddings.py  # BGE-M3 嵌入客户端
│   │   ├── schemas.py     # Pydantic 数据模型
│   │   └── schema_sql.py  # CREATE TABLE 语句
│   ├── engine/            # 核心引擎
│   │   ├── episode_loop.py    # 逐集理解主循环
│   │   ├── action_plan.py     # Action Plan 解析+执行
│   │   ├── state_patch.py     # Patch 缓冲+提交+冲突检测
│   │   ├── episode_types.py   # 类型定义
│   │   └── reporting.py       # Markdown 报告生成
│   └── tools/             # Action Handler 实现
│       ├── asset_tools.py     # ffmpeg 截帧
│       ├── memory_tools.py    # upsert_character, update_relationship
│       ├── query_tools.py     # get_character_card, search_events
│       ├── validation_tools.py# mark_uncertain, 冲突标记
│       └── normalizers.py     # 数据标准化
├── interaction_designer/  # 互动设计 Agent
│   ├── agent.py           # InteractionDesignAgent 主入口
│   ├── pass1_global.py    # 全局节奏分析
│   ├── pass2_episode.py   # 逐集互动点编排
│   ├── component_library.py   # 12 组件定义库
│   ├── safety_rules.py    # 安全规则+自动修复
│   ├── context_builder.py # 上下文组装
│   ├── output_formatter.py# 输出格式化+时长推断
│   └── manifest_writer.py # Manifest 写入
├── interaction_generator/ # 互动生成器 (规则驱动，降级方案)
│   ├── pipeline.py        # 主 Pipeline
│   ├── event_to_highlight.py  # 剧情事件→高光点
│   ├── highlight_to_ip.py     # 高光点→互动点
│   ├── asr_analyzer.py    # ASR 关键句提取
│   └── manifest_writer.py # Manifest 写入
└── branch_narrative/      # 分支叙事 Agent
    ├── agent.py           # BranchNarrativeAgent 主入口
    ├── phase1_planning.py # DAG 路线规划
    ├── phase2_narrative.py# 每节点剧情扩写
    ├── phase3_visual.py   # 视觉提示词生成
    ├── phase4_validation.py# 质量校验
    ├── image_generator.py # 图像生成 (Stub，P2)
    └── output_writer.py   # 输出打包
```

## 2.3 Pipeline 任务依赖

```
intake_drama (project.initialize)
    │
    ├── batch_asr (全部集转录)
    │
    └── for each episode:
        │
        ├── EpisodeLoop.process_episode(ep_num)
        │   ├── load ASR text
        │   ├── build context (前集摘要 + 角色 + 线程)
        │   ├── Doubao VLM understand_episode()
        │   ├── parse Action Plan (JSON)
        │   ├── execute actions (update characters, events, threads)
        │   ├── commit state patches
        │   ├── save episode summary
        │   └── create snapshot
        │
        ├── [全部集完成后]
        │
        ├── InteractionDesignAgent.run()
        │   ├── pass1: global rhythm blueprint
        │   ├── pass2: per-episode interaction point design
        │   └── write ep_*.interactions.json
        │
        └── BranchNarrativeAgent.run() (可选)
            ├── phase1: DAG route planning
            ├── phase2: per-node narrative expansion
            ├── phase3: visual prompts
            ├── phase4: validation
            └── write expansion package
```

## 2.4 Stage 1: ASR 转录

**实现文件**：`drama_agent/asr/client.py`

- 接口：HTTP POST `{ASR_ENDPOINT}/transcribe`
- 输入：MP4 视频文件
- 输出：`ASRResult`（含 text, segments, sentences, vad_segments, emotion_segments, audio_events）
- 超时：180 秒
- 文件存储：`{project}/asr/ep{NN}.json`

**降级**：ASR 端点未配置时跳过，模型用纯视觉理解。Prompt 中标注 `(ASR unavailable)`。

## 2.5 Stage 2: VLM 视频理解（核心）

**实现文件**：`drama_agent/model/client.py`, `drama_agent/model/prompts.py`

### 2.5.1 Doubao API 调用

- 端点：方舟 Ark API (`https://ark.cn-beijing.volces.com/api/v3`)
- ≤50MB 视频：base64 编码 → `video_url` content block
- >50MB 视频：File API 上传 → `input_video` content block
- 帧率：0.3 fps（每 3 秒取一帧）
- 重试：429→60s×3, 5xx→30s×2, Timeout→×2

### 2.5.2 Prompt 结构

**System Prompt**（`SYSTEM_PROMPT`）：
- 角色：短剧内容分析专家
- 输出格式：严格 JSON Action Plan（约 20 种 action 类型）
- 约束：不得臆造信息、置信度标注、不确定性标记

**Episode Prompt**（`build_episode_prompt()`）：
- 当前集 ASR 全文（带时间戳）
- 已知角色列表（最多 20 个活跃角色）
- 开放剧情线程
- 上一集摘要
- 系列状态（总集数、当前进度）

### 2.5.3 Action Plan 输出

模型返回 JSON，包含：
- `episode_summary`：本集摘要（200 字）
- `mood`：情绪标签
- `cliffhanger`：悬念描述
- `actions[]`：结构化操作列表，每项含 `action_type` + `params`

**Action 类型**（约 20 种）：

| Action | 说明 | Handler |
|:---|:---|:---|
| `upsert_character` | 新增/更新角色 | `memory_tools.py` |
| `update_relationship` | 更新角色关系 | `memory_tools.py` |
| `add_plot_event` | 记录剧情事件 | `memory_tools.py` |
| `open_thread` | 开启剧情线程 | `memory_tools.py` |
| `close_thread` | 关闭剧情线程 | `memory_tools.py` |
| `mark_uncertain` | 标记不确定信息 | `validation_tools.py` |
| `flag_conflict` | 标记冲突 | `validation_tools.py` |
| `capture_frame` | 提取关键帧 | `asset_tools.py` |
| ... | ... | ... |

## 2.6 Stage 3: State Patch 提交

**实现文件**：`drama_agent/engine/state_patch.py`

- 所有 Action 产生的变更先进入 Patch 缓冲区
- `PatchCommitter` 按置信度分三级处理：
  - `HIGH (≥0.8)`：直接提交
  - `MEDIUM (0.5-0.8)`：标记后提交
  - `LOW (<0.5)`：记录日志，不提交
- 每集完成后创建 SQLite 快照 (`snapshots/after_ep{NN}.db`)
- 同步向量到 Qdrant（仅 characters 集合 — 见 §2.11 已知限制）

## 2.7 Stage 4: 互动设计 Agent

**实现文件**：`interaction_designer/agent.py`

### 2.7.1 双 Pass 设计

**Pass 1 — 全局节奏蓝图** (`pass1_global.py`)：
- 输入：全剧报告（report.json）
- 分析：情绪曲线、高光密度、题材特征
- 输出：`rhythm_blueprint.json` — 每集建议的互动类型分布和密度

**Pass 2 — 逐集互动点编排** (`pass2_episode.py`)：
- 输入：report.json + rhythm blueprint + 单集 ASR
- 输出：每集 interaction_points[]（5-12 个）
- 约束：12 组件选择规则 + 安全规则 + 多样性（连续 3 集不同组件集）

### 2.7.2 12 种互动组件

| 组件 ID | 名称 | 触发场景 | 交互方式 |
|:---|:---|:---|:---|
| `celebrate_confetti` | 开心放彩带 | 主角目标达成 | 点击释放礼花 |
| `anger_release` | 怒火宣泄 | 角色受辱 | 点击泄愤 |
| `tear_resonance` | 泪光共鸣 | 离别/悲伤 | 长按释放情绪 |
| `laugh_burst` | 笑出声 | 反差笑点 | 点击表达好笑 |
| `shatter_strike` | 碎屏暴击 | 反派被打脸 | 连点释放爽感 |
| `sugar_storm` | 满屏撒糖 | 暧昧升温 | 连续点击提高甜度 |
| `guardian_shield` | 守护加持 | 角色受伤/逆风 | 长按守护 |
| `team_cheer` | 站队助威 | 双方对峙 | 选择阵营+助威 |
| `prediction_card` | 剧情预测卡 | 反转前 | 选择剧情走向 |
| `clue_judge_card` | 线索判断卡 | 关键物品出现 | 判断是否为伏笔 |
| `episode_end_prediction` | 剧尾预测卡 | 集尾悬念 | 预测下一集 |
| `emotion_buffer` | 情绪缓冲通道 | 持续压抑片段 | 长按进入缓冲 |

### 2.7.3 安全规则

**实现文件**：`interaction_designer/safety_rules.py`

| 规则 | 说明 |
|:---|:---|
| R1 道德不对称 | 反派得逞场景禁用 celebrate_confetti |
| R2 荒谬非喜剧 | 非喜剧场景禁用 laugh_burst |
| R3 角色死亡 | 主要角色死亡禁用 sugar_storm |
| R4 性暗示 | 禁用所有强交互组件 |
| R5 暴力极端 | ≥3 级暴力禁用 guardian_shield |
| R6-G9 | 更多组件选择约束（见 SPEC 文档） |

### 2.7.4 降级方案

**互动生成器** (`interaction_generator/`) 提供规则驱动的降级路径：
- 当 LLM 设计不可用时，从 report.json 的 plot_events 直接转换
- `event_to_highlight.py`：剧情事件→高光点（规则映射）
- `highlight_to_ip.py`：高光点→互动点（模板匹配）
- 质量低于 LLM 设计，但保证基础可用

## 2.8 Stage 5: 分支叙事 Agent

**实现文件**：`branch_narrative/agent.py`

### 2.8.1 四阶段流程

| 阶段 | 文件 | 功能 |
|:---|:---|:---|
| Phase 1 | `phase1_planning.py` | LLM 规划故事 DAG：分支点、路线、结局 |
| Phase 2 | `phase2_narrative.py` | 每节点生成 200-400 字剧情扩写 |
| Phase 3 | `phase3_visual.py` | 为每节点生成文生图提示词 |
| Phase 4 | `phase4_validation.py` | 校验：OOC 检测、剧情一致性、字数 |

### 2.8.2 当前状态

- **Phase 1-4 的 LLM 调用逻辑完整**
- **图像生成** (`image_generator.py`)：`PlaceholderGenerator` 为 Stub（返回 `status="skipped"`），`SeedreamGenerator` 骨架存在但 `raise NotImplementedError`
- **DAG 降级**：`phase1_planning.py:_fallback_plan()` 返回硬编码模板（15 节点/3 路线/3 结局），在 LLM 返回空 JSON 时使用

## 2.9 产物规格

### 2.9.1 Project 目录结构

```
projects/{project_id}/
├── project.json              # 元数据
├── memory.db                 # SQLite 记忆库
├── qdrant/                   # Qdrant 本地存储
├── asr/ep{NN}.json           # 每集 ASR 结果
├── episodes/                 # 视频文件（可选）
├── assets/characters/        # 角色相关资产
├── assets/evidence/          # 关键帧证据
├── assets/frames/            # 提取的视频帧
├── snapshots/after_ep{NN}.db # 每集数据库快照
├── action_plans/ep{NN}.json  # 每集 Action Plan
├── patches/                  # State Patch 日志
├── logs/patches/             # 详细 Patch 记录
└── output/
    ├── report.json           # 完整理解报告
    ├── report.md             # Markdown 可读报告
    ├── characters.json       # 角色导出
    ├── relationships.json    # 关系导出
    ├── plot_events.json      # 剧情事件导出
    ├── plot_threads.json     # 剧情线程导出
    └── knowledge_base/       # 知识库导出
```

### 2.9.2 Outputs 目录（Manifest 产物）

```
outputs/{drama_id}/
├── rhythm_blueprint.json     # 全局节奏蓝图
└── ep_{NNN}.interactions.json # 每集互动清单
```

## 2.10 质量门控

见 SDD-07 完整定义。关键门控：

| Gate | 类型 | 检查内容 |
|:---|:---|:---|
| G1 | Hard | IP 时长 [5s, 20s] |
| G2 | Hard | key_line 和 key_visual 非空 |
| G3 | Hard | 单集 IP 数量 3-15 |
| G4 | Hard | 相邻 IP 间隔 ≥8s |
| G5 | Soft | 全剧组件多样性 (≥5 种) |
| G6 | Soft | 情绪覆盖 (≥3 种) |
| G7 | Hard | Manifest JSON Schema 校验 |

## 2.11 已知限制与改进方向

| 限制 | 影响 | 改进方向 |
|:---|:---|:---|
| 嵌入向量使用 SHA-256 哈希伪嵌入 | 语义搜索完全失效 | 立即切换到 Ollama BGE-M3 (SDD-01 D-011) |
| Qdrant 连接失败静默 no-op | 向量写入/搜索全部静默失败 | 添加健康检查 + 启动时显式报错 |
| 向量仅同步 characters 集合 | events/episode_contexts 集合永远为空 | 添加 events 和 summaries 同步逻辑 |
| 图像生成为空壳 | 角色立绘/徽章无法生成 | MVP 用占位图，P2 接入文生图 |
| Pipeline 无任务队列 | 无失败重试、无并行 | P1 迁移到 Celery |
| 分支叙事 DAG 降级模板静态 | 多剧可能生成相同叙事结构 | 至少用角色名/剧情关键词参数化模板 |
