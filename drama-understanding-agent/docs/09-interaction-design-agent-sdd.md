# SDD-09: Interaction Design Agent 系统设计

> 版本: v1.0-draft
> 日期: 2026-06-05
> 定位: 多 Agent 协作系统中的"互动导演"角色

---

## 1. 系统定位与边界

### 1.1 角色定义

| Agent | 职责 | 比喻 |
|-------|------|------|
| drama-understanding-agent | 理解剧情内容，建立世界模型 | **编剧** — "这部剧讲了什么" |
| interaction-design-agent | 设计用户互动体验 | **互动导演** — "观众在哪里参与、如何参与" |

两个 Agent 是**协作关系**，不是主从关系。理解 Agent 产出结构化世界知识，互动设计 Agent 消费这些知识做面向观众的决策。

### 1.2 架构原则

1. **理解与设计分离** — 剧情理解不关心前端组件，互动设计不重复看视频
2. **串行流水线** — 全剧理解完毕后，设计 Agent 才进场（上帝视角）
3. **LLM 自主判断** — 互动设计是创意工作，不用规则表硬编码，给模型足够自由度
4. **内置安全自检** — 审核逻辑作为 Agent 内部组件，不额外增加调用轮次
5. **精确时点来自上游** — drama-agent 在理解阶段就产出毫秒级互动候选点，设计 Agent 只做选用和编排

### 1.3 与已有 interaction_generator 的关系

当前 `src/interaction_generator/` 是一个**纯规则转换器** — 它用映射表把 plot_events 机械地转为 interaction_points。

新的 interaction-design-agent **取代**这个规则转换器的核心逻辑：
- `event_to_highlight.py` 的分类逻辑 → 由 LLM 自主判断
- `highlight_to_ip.py` 的组件映射 → 由 LLM 自主选择
- `config.py` 的映射表 → 变为 LLM 的知识输入（组件库说明书）
- `manifest_writer.py` → 保留，纯序列化逻辑不变

---

## 2. 数据流全景

```
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 1: drama-understanding-agent (已有 + 扩展)                    │
│                                                                     │
│  新增能力:                                                           │
│    ① ASR 调用 (include_timestamps + include_vad + include_emotion)   │
│    ② Prompt 扩展: 输出 candidate_interactions[]                      │
│                                                                     │
│  每集产出:                                                           │
│    action_plan.json:                                                │
│      - actions[] (原有: 角色/关系/事件/伏笔)                         │
│      - candidate_interactions[] (新增: 互动候选点)                   │
│    asr/ep{N}.json:                                                  │
│      - text, time_stamps[], vad_segments[], emotion_segments[]       │
│                                                                     │
│  全剧产出:                                                           │
│    output/report.json (角色/关系/事件/伏笔/摘要)                     │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ 全剧完成后
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Phase 2: interaction-design-agent (新建)                            │
│                                                                     │
│  ┌───────────────────────────────────────────┐                      │
│  │  Pass 1: 全剧建模 (单次 LLM 调用)          │                      │
│  │                                           │                      │
│  │  输入 (~35K tokens for 24集):              │                      │
│  │    • 全集摘要 (每集一句 logline)            │                      │
│  │    • 核心角色弧线 (5-10 个)                │                      │
│  │    • 伏笔表 (open/resolved)               │                      │
│  │    • 全剧情绪弧线 (每集 mood)              │                      │
│  │    • 题材/类型/基调                        │                      │
│  │                                           │                      │
│  │  输出:                                    │                      │
│  │    • 互动节奏蓝图                          │                      │
│  │      (每集: 定位/密度目标/情绪色彩/重点)    │                      │
│  │    • 全剧互动策略                          │                      │
│  │      (哪类组件侧重/情绪高潮集标记)          │                      │
│  └───────────────────────────────────────────┘                      │
│                          │                                          │
│                          ▼                                          │
│  ┌───────────────────────────────────────────┐                      │
│  │  Pass 2: 逐集设计 (每集一次 LLM 调用)      │                      │
│  │                                           │                      │
│  │  输入 (~8K tokens/集):                     │                      │
│  │    • 本集 candidate_interactions[]         │                      │
│  │    • 本集 ASR 时间戳 + 情绪段               │                      │
│  │    • 本集 summary + mood + cliffhanger     │                      │
│  │    • Pass 1 的节奏蓝图 (本集部分)           │                      │
│  │    • 组件库说明书 (固定知识)                │                      │
│  │    • 安全规则 (内置)                       │                      │
│  │                                           │                      │
│  │  输出:                                    │                      │
│  │    • interaction_points[] (最终版)          │                      │
│  │    • episode_end_interaction               │                      │
│  │      (predictions / character_voices /     │                      │
│  │       clue_summary)                        │                      │
│  └───────────────────────────────────────────┘                      │
│                          │                                          │
│                          ▼                                          │
│  ┌───────────────────────────────────────────┐                      │
│  │  输出序列化 (复用 manifest_writer.py)       │                      │
│  │                                           │                      │
│  │  outputs/{drama_id}/                       │                      │
│  │    ep_001.interactions.json                │                      │
│  │    ep_002.interactions.json                │                      │
│  │    ...                                    │                      │
│  └───────────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 1 扩展: drama-understanding-agent 改动

### 3.1 ASR 接入

新增 `src/drama_agent/asr/client.py`:

```python
@dataclass
class ASRConfig:
    endpoint: str = "http://localhost:10000"
    language: str = "Chinese"
    include_timestamps: bool = True
    include_vad: bool = True
    include_emotion: bool = True
    include_speakers: bool = False  # MVP 不需要

@dataclass
class ASRResult:
    text: str
    language: str
    time_stamps: list[dict]       # [{text, start_time, end_time}, ...]
    vad_segments: list[dict]      # [{start_ms, end_ms, ...}, ...]
    emotion_segments: list[dict]  # [{emotion, start_ms, end_ms, score}, ...]
    audio_events: list[dict]      # [{event_type, start_ms, end_ms, intensity}, ...]
```

调用方式: 每集视频发送到 ASR 服务，返回结构化时间戳。

存储格式: `projects/{id}/asr/ep{N}.json` (已有路径约定，补全内容):

```json
{
  "text": "完整识别文本",
  "language": "Chinese",
  "segments": [
    {"text": "你们示例王朝皇帝", "start_ms": 47230, "end_ms": 48900},
    {"text": "见了我们也要毕恭毕敬", "start_ms": 48900, "end_ms": 51200}
  ],
  "vad_segments": [
    {"start_ms": 0, "end_ms": 5200, "is_speech": true},
    {"start_ms": 5200, "end_ms": 7800, "is_speech": false}
  ],
  "emotion_segments": [
    {"emotion": "angry", "start_ms": 45000, "end_ms": 52000, "score": 0.87}
  ],
  "audio_events": [
    {"event_type": "energy_spike", "start_ms": 47000, "intensity": 0.9}
  ]
}
```

### 3.2 Prompt 扩展: candidate_interactions 输出

在现有 `build_episode_prompt()` 的 `## Required Output` 部分新增:

```json
{
  "episode_summary": "...",
  "mood": "...",
  "cliffhanger": "...",
  "actions": [...],
  "candidate_interactions": [
    {
      "start_ms": 47000,
      "end_ms": 55000,
      "anchor_line": "你们示例王朝皇帝见了我们也要毕恭毕敬",
      "emotion_type": "anger|sweet|funny|sad|shocking|satisfying|tense",
      "intensity": 0.9,
      "reason": "为什么观众在此处会有强烈情绪反应(一句话)",
      "visual_cue": "此刻画面中最有冲击力的视觉元素",
      "is_cliffhanger": false
    }
  ]
}
```

**关键设计**:
- `start_ms/end_ms` 来自 ASR 时间戳锚定 — Prompt 中注入了 ASR 带时间戳的台词，模型能直接引用精确时间
- `anchor_line` 是模型选出的代表性台词 — 用于后续 interaction-design-agent 理解该点的内容
- `emotion_type` 是**观众情绪**（不是角色情绪）— 这是互动设计的核心维度
- 模型做此判断的认知负担很低 — 它本来就在理解剧情，顺带判断"观众看到这里会有什么反应"

### 3.3 ASR 文本注入 Prompt 的格式变化

当前 `_load_asr()` 输出:
```
[00:47] 你们示例王朝皇帝见了我们也要毕恭毕敬
[00:51] 我呸！
```

扩展为带毫秒精度 + 情绪标记:
```
## Current Episode ASR (with timestamps)
[00:47.230-00:48.900] 你们示例王朝皇帝
[00:48.900-00:51.200] 见了我们也要毕恭毕敬  [emotion:angry@0.87]
[00:51.500-00:52.100] 我呸！
```

这样模型输出 `candidate_interactions` 时可以直接引用精确时间。

---

## 4. Phase 2: interaction-design-agent 详细设计

### 4.1 技术栈

| 项 | 选择 | 理由 |
|----|------|------|
| 推理模型 | Doubao-Seed (同 drama-agent) | 统一技术栈，按量计费无差异 |
| 输入模态 | 纯文本 (不看视频) | 所有视觉信息已由 drama-agent 结构化 |
| 框架 | 独立 Python 包 `interaction_designer/` | 与 drama_agent 同项目但独立模块 |
| 调用模式 | 同步，无 Agent Loop | 每次调用明确输入输出，不需要迭代 |

### 4.2 模块结构

```
src/interaction_designer/
├── __init__.py
├── config.py                 # 设计约束常量 + 组件库定义
├── agent.py                  # 主入口: 编排 Pass1 + Pass2
├── pass1_global.py           # 全剧建模 Prompt 构建 + 解析
├── pass2_episode.py          # 逐集设计 Prompt 构建 + 解析
├── component_library.py      # 组件库知识 (注入 Prompt 的参考资料)
├── safety_rules.py           # 内置审核规则 (LLM 自检 + 硬规则后处理)
├── context_builder.py        # 从 drama-agent 产出构建输入上下文
└── output_formatter.py       # 结构化输出 → Manifest JSON
```

### 4.3 Pass 1: 全剧建模

#### 4.3.1 上下文工程

输入数据按区块组织，确保模型高效扫描：

```
## 剧集基本信息
标题: 示例剧A
类型: 古装爽剧
总集数: 24
基调: 隐忍复仇 + 身份反转 + 打脸爽感

## 全集摘要
Ep01: 比武招亲告示传三国，皇帝忧心；角色X扮纨绔被皇帝撞见；蛮人嚣张被神秘高手击倒
Ep02: 臣子D复命确认高手非自己；皇帝令测试权贵子弟；角色X被纳入名单
Ep03: 角色X被父鞭打，闪回揭露继母毒杀生母真相，角色X隐忍十五年决心复仇
...
Ep24: (最终集摘要)

## 核心角色弧线
- 角色X: Ep1-5 伪装纨绔 → Ep5 撕下面具 → Ep6-12 逐步展露实力 → ...
- 黑衣侍卫(臣子D): Ep1 第一高手 → Ep5 被角色X震惊 → ...
- 反派C: Ep3 登场,阴谋暴露 → ...

## 情绪弧线
Ep01: 紧绷+嚣张      Ep02: 凝重+悬念
Ep03: 压抑+隐忍      Ep04: 紧张+戏谑反差
Ep05: 反转爽感拉满   ...

## 伏笔表
- [OPEN] 比武招亲护国主线 (Ep1起)
- [OPEN] 角色X真实身份之谜 (Ep1起，Ep5部分揭晓)
- [OPEN] 反派C毒杀生母 (Ep3揭露，未清算)
- [RESOLVED] 神秘高手身份 (Ep1埋，Ep5揭晓=角色X)
```

#### 4.3.2 Prompt 指令

```
你是一位短剧互动体验设计师。你的任务是为这部短剧制定全局互动节奏规划。

你需要考虑：
1. 哪些集是"高燃集"（适合密集互动）、哪些是"铺垫集"（互动克制，让观众专注剧情）
2. 全剧情绪走向如何分配互动类型（前期多悬念线索，中期多冲突对峙，后期多爽点释放）
3. 互动节奏不能单调 — 不能连续3集都是同一种互动主题
4. 集尾互动策略 — 哪些集适合预测题、哪些适合角色心声

输出 JSON:
{
  "drama_profile": {
    "genre": "...",
    "core_emotion": "...",
    "audience_expectation": "观众追这类剧想要什么情绪满足"
  },
  "rhythm_blueprint": [
    {
      "episode_num": 1,
      "positioning": "铺垫集|过渡集|高燃集|情感集|反转集",
      "interaction_density": "low|medium|high",
      "primary_emotion": "本集互动主打情绪",
      "emphasis": "本集互动设计重点(一句话)",
      "end_interaction_type": "prediction|character_voice|clue_review|none"
    }
  ],
  "global_strategy": {
    "component_distribution": "全剧组件使用策略说明",
    "escalation_plan": "互动强度如何随剧情递增"
  }
}
```

#### 4.3.3 Token 预算分析

| 数据块 | 24集估算 | 5集实测 |
|--------|---------|--------|
| 剧集基本信息 | ~200 | ~200 |
| 全集摘要 (每集40字 logline) | ~1600 | ~350 |
| 核心角色弧线 (10角色×50字) | ~800 | ~400 |
| 情绪弧线 | ~500 | ~100 |
| 伏笔表 | ~600 | ~200 |
| Prompt 指令 | ~1500 | ~1500 |
| **总输入** | **~5200** | **~2750** |
| 预期输出 | ~3000 | ~800 |
| **单次调用总量** | **~8200** | **~3550** |

**结论: 24集全剧建模一次调用约 8K tokens，完全无压力。**

即使是 100 集长剧（每集 logline 40字 = 4000字摘要），总输入也只约 15K tokens，远低于 128K 窗口。

### 4.4 Pass 2: 逐集设计

#### 4.4.1 输入构建

```
## 全剧节奏蓝图 (本集)
集数: 5
定位: 高燃集
互动密度: high
主打情绪: satisfying (反转爽感)
设计重点: 角色X撕下伪装的高光时刻，释放前4集积累的隐忍压力
集尾互动: prediction (对决结果悬念强烈)

## 本集候选互动点 (来自 drama-understanding-agent)
[
  {
    "start_ms": 0,
    "end_ms": 30000,
    "anchor_line": "你的按摩手法今天不错嘛",
    "emotion_type": "funny",
    "intensity": 0.6,
    "reason": "侍卫假扮侍女给角色X按摩的反差喜感",
    "visual_cue": "角色X眼贴黄瓜片泡澡，全然不知身后是杀手"
  },
  {
    "start_ms": 60000,
    "end_ms": 75000,
    "anchor_line": "我的命可以给你，这个玉佩不行",
    "emotion_type": "sad",
    "intensity": 0.85,
    "reason": "角色X对生母遗物的极致珍视触动观众",
    "visual_cue": "角色X紧握玉佩，眼神坚定"
  },
  {
    "start_ms": 91000,
    "end_ms": 108000,
    "anchor_line": "要么留下玉佩，要么留下你的命",
    "emotion_type": "satisfying",
    "intensity": 0.95,
    "reason": "角色X彻底撕下伪装，绝顶轻功飞上屋顶拦路",
    "visual_cue": "白衣角色X凌空飞落屋顶，冷眼俯视黑衣侍卫"
  }
]

## 本集 ASR 情绪段
[45s-52s] emotion=neutral  [60s-75s] emotion=sad@0.82
[91s-108s] emotion=angry@0.91

## 本集 ASR 高情绪台词
[01:31.200] "要么留下玉佩" (angry@0.91)
[01:00.500] "我的命可以给你" (sad@0.82)

## 可用组件库 (固定知识注入)
(见 §4.5)
```

#### 4.4.2 Prompt 指令

```
你是互动导演。请为本集设计最终的互动方案。

你的决策权包括：
1. 从候选互动点中【选择】哪些保留（不必全选，也可全选）
2. 为每个保留的点【分配】最合适的前端组件
3. 设计每个互动点的【情绪标注】和【触发理由】
4. 设计【集尾互动】（预测题/角色心声/线索回顾）
5. 调整【时间窗口】确保互动不重叠

设计原则：
- 互动是为了放大观众的情绪体验，不是打断观看
- 一集最多 8 个互动点，最少 3 个
- 相邻两个互动点间隔至少 10 秒
- 同一组件不连续使用超过 2 次
- 集尾预测题的答案必须在下一集可验证
- 互动强度应跟随剧情节奏递增，高潮在后半段

安全自检：
- 悲伤/压抑场景不使用 shatter_strike 或 celebrate_confetti
- 甜蜜场景不使用 anger_release
- 暴力/敏感场景的 intensity 不超过 0.8
- 所有 start_ms < end_ms，且 end_ms - start_ms 在 [5000, 20000] 之间

输出 JSON:
{
  "interaction_points": [
    {
      "id": "ip_ep_005_0001",
      "start_ms": 0,
      "end_ms": 9000,
      "component": "(从组件库中选择)",
      "emotion": "(观众此刻的情绪)",
      "intensity": 0.0-1.0,
      "priority": 0.0-1.0,
      "confidence": 0.0-1.0,
      "key_line": "代表性台词",
      "key_visual": "一句话视觉描述",
      "highlight_reason": "为什么在此处触发互动(面向审核人员的解释)",
      "score_type": "resonance|guard|plot|insight|cocreate",
      "config": {}
    }
  ],
  "episode_end_interaction": {
    "predictions": [...],
    "character_voices": [...],
    "clue_summary_enabled": true/false
  },
  "design_notes": "本集互动设计思路说明(2-3句)"
}
```

### 4.5 组件库说明书 (Component Library)

作为固定知识注入每次 Pass 2 的 Prompt:

```markdown
## 可用互动组件

### 碎屏暴击 (shatter_strike)
适用场景: 反派被打脸、主角复仇成功、爽点释放
观众情绪: satisfying
触觉反馈: sharp_click
粒子效果: shatter (碎片飞溅)
时长建议: 5-9秒
成长机制: 连续点击屏幕裂痕扩大

### 生气宣泄 (anger_release)
适用场景: 角色被欺压、不公正对待、观众想替角色出气
观众情绪: angry
触觉反馈: heavy_tap
时长建议: 5-9秒
成长机制: 点击释放怒气值

### 撒糖风暴 (sugar_storm)
适用场景: CP互动、表白、拥抱、甜蜜时刻
观众情绪: sweet
粒子效果: heart / sugar
时长建议: 7-12秒
成长机制: 点击飘落更多糖果/爱心

### 站队助威 (team_cheer)
适用场景: 双方对峙、阵营选择、观众想表态
观众情绪: support
时长建议: 8-15秒
特殊配置: 需要 team_options (两个阵营)
成长机制: 实时人数对比

### 守护加持 (guardian_shield)
适用场景: 角色处于危险、需要保护、观众想守护
观众情绪: guard
粒子效果: shield
时长建议: 5-9秒

### 剧情预测 (prediction_card)
适用场景: 反转前夕、悬念升起、即将揭晓真相
观众情绪: curious
时长建议: 10-15秒
特殊配置: 需要 question + options (2-3个选项)
答案要求: 必须在后续集数中可验证

### 线索判断 (clue_judge_card)
适用场景: 埋伏笔时刻、关键物品出现、可疑行为
观众情绪: insight
时长建议: 8-12秒
特殊配置: 需要 question + options

### 庆祝礼炮 (celebrate_confetti)
适用场景: 角色胜利、目标达成、大团圆
观众情绪: happy
粒子效果: confetti
时长建议: 5-8秒

### 泪点共鸣 (tear_resonance)
适用场景: 感人离别、牺牲、回忆杀、情感爆发
观众情绪: moved
时长建议: 8-12秒
注意: 不要在角色死亡瞬间触发（给观众消化时间）

### 大笑互动 (laugh_burst)
适用场景: 搞笑反差、尴尬名场面、喜剧桥段
观众情绪: funny
时长建议: 5-8秒

### 情绪缓冲 (emotion_buffer)
适用场景: 高压之后的喘息、过渡段落
观众情绪: calm
时长建议: 5-8秒
注意: 仅作为兜底，优先使用更具体的组件

### 剧尾预测 (episode_end_prediction)
适用场景: 集尾悬念点
观众情绪: anticipation
特殊配置: 与 prediction_card 相同，但固定在集尾出现
```

### 4.6 安全自检规则 (Safety Rules)

作为 Prompt 的一部分直接注入（不额外调用），加上硬规则后处理:

#### 4.6.1 LLM 自检 (Prompt 内)

上文 §4.4.2 的"安全自检"部分已注入。模型会在输出时自行遵守。

#### 4.6.2 硬规则后处理 (代码)

```python
def validate_manifest(manifest: dict) -> list[str]:
    """返回违规列表，空表示通过"""
    violations = []
    points = manifest["interaction_points"]
    
    # G1: 时长约束
    for p in points:
        duration = p["end_ms"] - p["start_ms"]
        if duration < 5000 or duration > 20000:
            violations.append(f"G1: {p['id']} duration={duration}ms out of [5s,20s]")
    
    # G4: 重叠检测
    for i in range(len(points) - 1):
        gap = points[i+1]["start_ms"] - points[i]["end_ms"]
        if gap < 0:
            violations.append(f"G4: {points[i]['id']} overlaps {points[i+1]['id']}")
    
    # G6: 数量上限
    if len(points) > 12:
        violations.append(f"G6: {len(points)} points exceeds max 12")
    
    # G7: 组件多样性
    components = [p["component"] for p in points]
    if len(set(components)) < 2 and len(points) >= 3:
        violations.append(f"G7: only 1 component type used")
    
    # G9: 预测题可验证
    for pred in manifest.get("episode_end_interaction", {}).get("predictions", []):
        if not pred.get("answer_key"):
            violations.append(f"G9: prediction missing answer_key")
    
    return violations
```

违规处理:
- hard_fail (G1/G4/G6) → 自动修正（裁切时长/移除重叠/截断）
- soft_warn (G7) → 记录到 warnings，不阻塞

---

## 5. ASR 接入方案

### 5.1 调用时机

在 `EpisodeLoop.process_episode()` 中，**先于 VLM 调用**:

```python
def process_episode(self, episode_num: int) -> ExecutionResult:
    # Step 1: ASR (先行)
    asr_result = self.asr_client.transcribe(ctx.video_path)
    self._save_asr(episode_num, asr_result)
    
    # Step 2: 构建上下文 (含 ASR 时间戳)
    ctx = self.build_context(episode_num)  # 现在 ctx.asr_text 包含带时间戳格式
    
    # Step 3: VLM 理解 (Prompt 中含 ASR 时间戳 + 要求输出 candidate_interactions)
    prompt = build_episode_prompt(ctx, ...)
    raw_response = self.model.understand_episode(ctx.video_path, prompt, SYSTEM_PROMPT)
    ...
```

### 5.2 ASR 结果格式化

为 VLM Prompt 注入的格式:

```python
def format_asr_for_prompt(asr_result: ASRResult) -> str:
    lines = ["## Current Episode ASR (timestamped)"]
    for seg in asr_result.time_stamps:
        start = format_ms_precise(seg["start_time"])
        end = format_ms_precise(seg["end_time"])
        text = seg["text"]
        # 如果该时间段有情绪标记，附加
        emotion_tag = find_emotion_at(asr_result.emotion_segments, seg["start_time"])
        tag = f"  [{emotion_tag}]" if emotion_tag else ""
        lines.append(f"[{start}-{end}] {text}{tag}")
    return "\n".join(lines)

def format_ms_precise(seconds: float) -> str:
    """00:47.230"""
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m:02d}:{s:06.3f}"
```

### 5.3 容错

- ASR 服务不可用 → 降级为无时间戳模式（VLM 用 MM:SS 粗定位，同当前行为）
- ASR 返回空 → 视频可能无对白（纯音乐/动作），标记 `asr_available=false`
- 情绪模型未加载 → `emotion_segments` 为空，不影响核心流程

---

## 6. 编排层: 两个 Agent 的串联

### 6.1 CLI 命令

```bash
# 完整流程: 理解 + 设计
drama-agent full-pipeline \
  --title "示例剧A" \
  --video-dir ./videos \
  --episodes 24

# 仅理解 (已有)
drama-agent understand \
  --title "示例剧A" \
  --video-dir ./videos \
  --episodes 24

# 仅设计 (新增，基于已有理解产出)
drama-agent design-interactions \
  --project test-5eps \
  --output ./outputs
```

### 6.2 full-pipeline 流程

```python
def full_pipeline(config):
    # Phase 1: 全集理解
    understanding_loop = EpisodeLoop(config)
    understanding_result = understanding_loop.run()
    
    # Phase 2: 互动设计
    designer = InteractionDesignAgent(config)
    design_result = designer.run(
        project_dir=config.output_dir,
        output_dir=config.output_dir / "interactions",
    )
    
    return {
        "understanding": understanding_result,
        "interactions": design_result,
    }
```

---

## 7. 成本估算

### 7.1 单部短剧 (24集) 完整流程

| 阶段 | 调用次数 | 每次 tokens (in+out) | 总 tokens |
|------|---------|---------------------|-----------|
| ASR (本地GPU) | 24 | 0 (本地推理) | 0 |
| VLM 理解 (含 candidate_interactions) | 24 | ~4000 in + ~3000 out | ~168K |
| Pass 1 全剧建模 | 1 | ~5000 in + ~3000 out | ~8K |
| Pass 2 逐集设计 | 24 | ~8000 in + ~2000 out | ~240K |
| **总计** | 49 次 LLM 调用 | | **~416K tokens** |

### 7.2 对比当前 (仅理解，无互动设计)

| 阶段 | 总 tokens |
|------|-----------|
| VLM 理解 (当前) | 24 × ~5000 = ~120K |

新增成本: 约 296K tokens (~2.5 倍)。但考虑到 VLM 理解阶段只是多输出一个 `candidate_interactions` 字段（增加 ~500 tokens/集），真正的新增主要在 Pass 2 的 240K。

### 7.3 优化空间

如果成本敏感:
- Pass 2 可以 batch 处理（2-3 集合并一次调用），但会牺牲单集设计精度
- Pass 1 对短剧（<10集）可以跳过，直接进 Pass 2
- candidate_interactions 数量可以限制为每集最多 5 个，减少 Pass 2 输入

---

## 8. 目录结构 (最终)

```
drama-understanding-agent/
├── src/
│   ├── drama_agent/              # Phase 1: 理解系统 (已有 + 扩展)
│   │   ├── asr/                  # 新增: ASR 客户端
│   │   │   ├── __init__.py
│   │   │   └── client.py        # ASR HTTP client
│   │   ├── engine/
│   │   │   └── episode_loop.py  # 修改: 集成 ASR 调用
│   │   ├── model/
│   │   │   └── prompts.py       # 修改: 新增 candidate_interactions 输出
│   │   └── ...
│   │
│   ├── interaction_designer/     # 新增: Phase 2 互动设计 Agent
│   │   ├── __init__.py
│   │   ├── agent.py             # 主入口
│   │   ├── config.py            # 设计约束
│   │   ├── pass1_global.py      # 全剧建模
│   │   ├── pass2_episode.py     # 逐集设计
│   │   ├── component_library.py # 组件库知识
│   │   ├── safety_rules.py      # 审核规则
│   │   ├── context_builder.py   # 输入构建
│   │   └── output_formatter.py  # 输出格式化
│   │
│   └── interaction_generator/    # 保留: 纯规则转换器 (降级路径)
│       └── ...
│
├── docs/
│   ├── 09-interaction-design-agent-sdd.md  # 本文档
│   └── ...
└── ...
```

---

## 9. 实施路径

### Phase A: ASR 接入 + Prompt 扩展 (drama-agent 改动)

```
任务:
1. 新建 src/drama_agent/asr/client.py — ASR HTTP 客户端
2. 修改 config.py — 新增 asr_endpoint 配置
3. 修改 episode_loop.py — 在 process_episode 中先调 ASR
4. 修改 prompts.py — ASR 注入格式 + candidate_interactions 输出要求
5. 修改 action_plan.py — 解析 candidate_interactions 字段
6. 修改 reporting.py — 报告中包含 candidate_interactions 统计
```

### Phase B: interaction-design-agent 实现

```
任务:
1. 新建 src/interaction_designer/ 完整模块
2. 实现 pass1_global.py — 全剧建模 Prompt + 解析
3. 实现 pass2_episode.py — 逐集设计 Prompt + 解析
4. 实现 component_library.py — 组件库知识文本
5. 实现 safety_rules.py — 硬规则后处理
6. 实现 context_builder.py — 从 report.json 构建输入
7. 实现 agent.py — 编排 Pass1 + Pass2 循环
```

### Phase C: 集成与测试

```
任务:
1. CLI 新增 design-interactions 和 full-pipeline 命令
2. 用 test-5eps 数据端到端测试
3. 输出 Manifest 对接 OFFLINE_VIDEO_UNDERSTANDING_OUTPUT_SPEC 格式
4. 验证前端可消费
```

---

## 10. 关键设计决策记录 (ADR)

### ADR-1: 为什么不让 interaction-design-agent 看视频

**决策**: 互动设计 Agent 只消费结构化数据，不调用 VLM。

**理由**:
- drama-agent 已经完成了视觉信息的结构化（plot_events + candidate_interactions 含 visual_cue）
- 重复看视频是 token 浪费（24集 × VLM = 额外 ~120K tokens）
- 互动设计是"策略决策"不是"感知任务"，不需要原始像素

### ADR-2: 为什么用 LLM 自主判断而非规则表

**决策**: 互动组件选择由 LLM 自主决定，规则只做安全兜底。

**理由**:
- 情绪共鸣是复杂判断（"角色X隐忍十五年终于爆发"对应什么组件？碎屏暴击还是守护加持？取决于叙事角度）
- 规则表只能覆盖显然的映射，边界 case 需要理解力
- LLM 可以考虑"节奏感"和"前后对比"，规则表做不到

### ADR-3: 为什么 Pass 1 用全量输入而不压缩

**决策**: 24集全集摘要 + 角色 + 伏笔直接输入，不做 RAG 检索。

**理由**:
- 实测全量 ~5K-8K tokens，远低于 128K 窗口
- 全局建模需要"看到全貌"，RAG 会丢失跨集对比信息
- 即使 100 集长剧也只 ~15K tokens，无需压缩

### ADR-4: 为什么保留 interaction_generator 作为降级路径

**决策**: 旧的规则转换器保留，作为 LLM 不可用时的 fallback。

**理由**:
- 纯规则转换不依赖 LLM API，100% 可用
- 产出质量低但格式正确，前端能消费
- 成本为 0

---

> **本文档定义了 interaction-design-agent 的完整规格。执行时按 Phase A → B → C 顺序实施。每个 Phase 独立可测试。**
