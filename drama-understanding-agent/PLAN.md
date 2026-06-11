# Drama Understanding Agent - 实现计划

## 设计目标

将当前 `server/pipeline_stages/` 中的逐集独立 VLM 理解流程重构为一个以 Agent 范式驱动的多集连续剧情理解系统。

## 核心原则

1. **Project 隔离优先** - 每部短剧一个独立记忆空间
2. **全模态模型负责理解，系统负责记忆治理** - 不堆叠脆弱视觉流水线
3. **每集输出 Action Plan** - 模型主动告诉系统需要执行什么操作
4. **State Patch 缓冲** - 所有更新先进入暂存区，不直接污染长期记忆
5. **Full-Auto 优先** - MVP 先跑通全自动，HITL 后续加入
6. **一次性输入全部视频，按剧集顺序迭代理解**

---

## 文档体系 (已完成)

| 文档 | 内容 | AI Coding 工具如何使用 |
|------|------|----------------------|
| `docs/00-architecture.md` | 总体架构、数据流、ADR、技术栈 | 理解全貌，不迷路 |
| `docs/01-memory-system.md` | SQLite Schema、Qdrant Collection、查询接口 | 照着 Schema 建表，照着接口实现 |
| `docs/02-model-interface.md` | API 格式、Prompt 模板、容错策略 | 照着模板组装请求，照着策略处理错误 |
| `docs/03-action-plan-engine.md` | Action 类型、执行器映射、JSON 容错 | 逐个实现 handler |
| `docs/04-state-patch.md` | Patch 结构、置信度规则、提交策略、快照 | 实现提交和回滚逻辑 |
| `docs/05-episode-loop.md` | 主循环、上下文构建、报告生成、CLI | 串联所有模块 |
| `docs/06-v2-iteration.md` | **V2 迭代计划**：bug修复 + 向量激活 + 报告丰富化 | ✅ 已完成 |
| `docs/07-alignment-audit.md` | V2 完成后设计对齐审核报告 | 参考，确认系统状态 |
| `docs/08-interaction-generator.md` | 前端对接方案初稿（规则转换器） | 已被 09 取代，保留作降级参考 |
| `docs/09-interaction-design-agent-sdd.md` | **互动设计 Agent SDD**：多Agent协作 + ASR接入 + LLM自主设计 | 🔥 当前任务，按 Phase A→B→C 执行 |

---

## 代码结构

```
drama-understanding-agent/
├── PLAN.md                          # 本文件
├── docs/                            # 规格文档 (6份)
├── src/
│   ├── drama_agent/
│   │   ├── __init__.py
│   │   ├── config.py                # 项目配置 (Pydantic Settings)
│   │   ├── project.py               # Project 管理（目录创建、快照、隔离）
│   │   ├── memory/                   # 记忆系统
│   │   │   ├── __init__.py
│   │   │   ├── store.py             # SQLite CRUD
│   │   │   ├── vectors.py           # Qdrant 封装
│   │   │   └── schemas.py           # Pydantic 数据模型
│   │   ├── model/                    # 模型接口
│   │   │   ├── __init__.py
│   │   │   ├── client.py            # Doubao API 客户端
│   │   │   └── prompts.py           # Prompt 模板
│   │   ├── engine/                   # 核心引擎
│   │   │   ├── __init__.py
│   │   │   ├── action_plan.py       # Action Plan 解析 + 执行
│   │   │   ├── state_patch.py       # Patch 缓冲 + 提交 + 冲突检测
│   │   │   └── episode_loop.py      # 逐集理解主循环
│   │   └── tools/                    # 工具链 (Action Handler 实现)
│   │       ├── __init__.py
│   │       ├── asset_tools.py       # capture_frame (ffmpeg)
│   │       ├── memory_tools.py      # upsert_character, update_relationship, ...
│   │       ├── query_tools.py       # 检索类 (get_character_card, search_events)
│   │       └── validation_tools.py  # mark_uncertain, 冲突标记
│   └── cli.py                        # 命令行入口 (typer/click)
├── tests/
│   ├── test_memory_store.py
│   ├── test_action_plan_parse.py
│   ├── test_state_patch.py
│   └── test_episode_loop.py
├── pyproject.toml
└── .env.example
```

---

## 实现顺序 (给 AI Coding 工具的任务拆分)

### Phase 1: 骨架 (预计 1 次 session)
1. `pyproject.toml` + `.env.example` + 依赖声明
2. `config.py` - Pydantic Settings，读取 .env
3. `schemas.py` - 所有 Pydantic 数据模型
4. `project.py` - 项目目录管理、快照

### Phase 2: 记忆系统 (预计 1 次 session)
5. `store.py` - SQLite 建表 + CRUD 全套
6. `vectors.py` - Qdrant collection 创建 + 增删查

### Phase 3: 模型接口 (预计 1 次 session)
7. `client.py` - Doubao API 封装（视频/图像/文本）
8. `prompts.py` - System Prompt + Episode Prompt 模板

### Phase 4: 引擎 (预计 1-2 次 session)
9. `action_plan.py` - JSON 解析 + 执行器映射 + 分发
10. `state_patch.py` - Patch 生成 + 置信度 + 提交 + 冲突检测
11. `tools/memory_tools.py` - 各 handler 实现
12. `tools/asset_tools.py` - ffmpeg 截帧
13. `tools/validation_tools.py` - 标记逻辑

### Phase 5: 主循环 + CLI (预计 1 次 session)
14. `episode_loop.py` - 完整循环逻辑
15. `cli.py` - 命令行入口
16. 端到端测试

---

## 关键依赖

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "httpx>=0.27",           # API 调用
    "pydantic>=2.0",         # 数据模型
    "pydantic-settings>=2.0",# 配置管理
    "qdrant-client>=1.9",    # 向量存储
    "json-repair>=0.30",     # JSON 修复
    "typer>=0.12",           # CLI
    "rich>=13.0",            # 终端美化输出
]
```

---

## 与现有系统的关系

- **取代**: `s1_understand.py`, `s1_vlm.py`, `s2_summarize.py`, `s2_narrative.py`
- **复用**: ASR 结果 (由现有 `s1_asr.py` 生成的 `asr.json`)
- **产出被消费**: 下游 `s3_highlight.py`, `s4_orchestrate.py`, `s6_expansion.py` 可从本系统的 SQLite + JSON 中获取数据
- **物理隔离**: 独立目录 `drama-understanding-agent/`，独立虚拟环境，通过文件系统交接

---

## AI Coding 使用指南

当你用 Claude Code 实现本项目时：

1. **先读对应的 docs/ 文件** - 每个模块的规格都在对应文档中
2. **一次只做一个 Phase** - 不要试图一次写完所有代码
3. **文件不超过 300 行** - 如果超过，拆分
4. **每个模块写完跑一次测试** - 确保能独立工作
5. **不要引入文档中没提到的依赖** - 保持最小化
6. **Prompt 模板是核心** - 花时间调优，不要草率

如果遇到不确定的设计决策，回来查 `docs/00-architecture.md` 中的 ADR 章节。
