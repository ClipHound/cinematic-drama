# Branch Narrative Agent - 设计文档 (SDD)

> 分支剧情续写 Agent：在全剧最后一集结束后，为用户提供选择驱动的多分支剧情体验
> 日期: 2026-06-10
> 驱动模型: Doubao Seed 2.0 Lite (文本生成 + 理解)
> 图片生成: Seedream 系列 (接口预留，当前不实际调用)

---

## 1. 产品定义

### 1.1 是什么

用户看完短剧最后一集后，进入"分支剧情"模式。系统展示一段过渡叙事（承接正片结尾），然后给出 2-3 个选项。用户选择后，剧情向不同方向推进，再次给出选项，如此重复 4-5 次，最终收敛到 3 个不同结局之一。

### 1.2 不是什么

- **不是** 用户自由输入续写（不是 chatbot）
- **不是** 每次用户选择都实时调用 AI 生成（是预生成的静态数据包）
- **不是** 独立故事，而是承接全剧理解结果的延续
- **不是** 每个选择都产生全新分支（用收敛机制控制节点总数）

### 1.3 运行模式

```
视频理解完成 → 互动设计完成 → [Branch Narrative Agent 运行一次] → 输出静态数据包
                                                                    ↓
                                                        前端按数据包导航用户选择
```

和 interaction-design-agent 一样：**离线生成，一次运行，伴随该剧永久生效**。

---

## 2. 收敛架构：状态标签 DAG

### 2.1 核心问题

如果每个选择点有 2 个选项，N 次选择后分支数 = 2^N：
- 4 次选择 → 16 条路径 → 16 个结局 ❌ 制作成本爆炸

### 2.2 解决方案：状态标签 + DAG 汇合

**不用树，用有向无环图 (DAG)**。关键机制：

1. **状态标签**：每个节点不记录完整路径历史，只携带当前"路线标签"
2. **汇合节点**：不同选择路径如果导向相同标签状态，汇入同一个后续节点
3. **固定结局数**：最终只有 3 个结局，所有路径必须收敛到其中之一

### 2.3 具体规格

| 参数 | 值 | 说明 |
|------|---|------|
| 选择次数 | 4-5 次 | 用户做 4-5 次选择后到达结局 |
| 每次选项数 | 2-3 个 | 通常 2 个，关键节点可 3 个 |
| 结局数 | 3 个 | 固定 3 个差异化结局 |
| 内容节点总数上限 | 25 个 | 包含所有层的叙事段落 |
| 路线标签数 | 3 条 | 如 `光明线 / 暗影线 / 隐士线` |

### 2.4 DAG 结构示意

```
                    Layer 0 (开场过渡)
                         [N0]
                        /    \
               选择A         选择B
                /               \
         Layer 1                Layer 1
        [N1a]                  [N1b]
       /     \                /     \
    选择A   选择B          选择A   选择B
     /         \            /         \
Layer 2      Layer 2(汇合!)       Layer 2
[N2a]         [N2b]              [N2c]
  ↑              ↑                 ↑
光明线          暗影线            隐士线
  |            /    \              |
  ↓          ↓      ↓             ↓
Layer 3    Layer 3  Layer 3    Layer 3
[N3a]     [N3b]   [N3c]      [N3d]
   \        |      /            |
    ↓       ↓    ↓              ↓
     结局A    结局B           结局C
```

**汇合规则**：
- N1a 的选择B 和 N1b 的选择A 如果导向相同路线标签 → 汇入同一个 N2b
- Layer 2 之后，每条路线标签对应 1 个节点（不再分裂）
- Layer 3 → 结局 是确定性映射（路线标签直接决定结局）

### 2.5 收敛公式

```
Layer 0: 1 个节点 (开场)
Layer 1: 2-3 个节点 (首次分叉，路线尚未确定)
Layer 2: 3 个节点 (路线确定，汇合完成)
Layer 3: 3-4 个节点 (路线内微调，但不改变结局方向)
Layer 4: 3 个节点 (结局前奏)
结局层: 3 个节点

总计: 1 + 3 + 3 + 4 + 3 + 3 = 17 个内容节点 (在 25 上限内)
```

### 2.6 状态标签机制

每个选项携带 `tag_effect`：

```json
{
  "option_text": "亲自前去与蛮夷谈判",
  "tag_effect": {"justice": +2, "shadow": 0, "hermit": -1},
  "next_node": "n_layer2_justice"
}
```

前端不需要复杂逻辑——每个选项直接指向下一个 node_id。标签只是 **Agent 生成时的内部决策工具**，最终产出的 DAG 已经是确定性的（每个选项 → 确定的下一节点）。

---

## 3. 数据结构

### 3.1 输出: Branch Narrative Package

```json
{
  "drama_id": "example-drama-a",
  "branch_narrative_version": "1.0",
  "generated_at": "2026-06-10T...",
  "metadata": {
    "total_nodes": 17,
    "total_choices": 5,
    "endings_count": 3,
    "route_tags": ["justice", "shadow", "hermit"]
  },
  "entry_node": "n_opening",
  "nodes": {
    "n_opening": { ... },
    "n_l1_a": { ... },
    ...
  },
  "endings": {
    "ending_justice": { ... },
    "ending_shadow": { ... },
    "ending_hermit": { ... }
  }
}
```

### 3.2 Node 结构

```json
{
  "node_id": "n_l1_a",
  "layer": 1,
  "route_tag": "justice",
  "narrative": {
    "title": "角色X决定公开身份",
    "paragraphs": [
      "比武招亲大典将近，角色X站在铜镜前...",
      "他缓缓解开束发的丝带..."
    ],
    "scene_description": "镇北侯府，清晨，角色X的卧房",
    "characters_present": ["角色X", "小翠"],
    "mood": "resolute"
  },
  "visual": {
    "prompt": "古装男子独立铜镜前，解开束发，露出凌厉眼神，清晨光线从窗棂射入，暖色调，电影感构图",
    "reference_images": ["assets/characters/ep05_角色X_0142.jpg"],
    "style_tags": ["cinematic", "warm_light", "ancient_chinese", "close_up"]
  },
  "choices": [
    {
      "choice_id": "c_l1_a_1",
      "option_text": "在比武场上当众揭穿反派C的阴谋",
      "option_subtext": "正面对决，但可能打草惊蛇",
      "leads_to": "n_l2_justice"
    },
    {
      "choice_id": "c_l1_a_2",
      "option_text": "先暗中收集证据，等时机成熟再出手",
      "option_subtext": "稳妥但需要继续忍耐",
      "leads_to": "n_l2_shadow"
    }
  ],
  "audio_hint": {
    "bgm_mood": "tense_anticipation",
    "sfx_suggestion": "fabric_rustling, mirror_reflection"
  }
}
```

### 3.3 Ending 结构

```json
{
  "ending_id": "ending_justice",
  "ending_title": "光明正道",
  "ending_subtitle": "角色X以正义之名夺回一切",
  "narrative": {
    "paragraphs": ["...", "..."],
    "scene_description": "...",
    "mood": "triumphant"
  },
  "visual": {
    "prompt": "...",
    "reference_images": ["..."],
    "style_tags": ["..."]
  },
  "epilogue": "三个月后，示例王朝国...",
  "character_fates": {
    "角色X": "成为镇北侯，守护示例王朝",
    "反派C": "被揭穿罪行，流放边疆",
    "苏明武": "真心悔改，成为角色X副将"
  }
}
```

---

## 4. Agent 架构

### 4.1 系统定位

```
┌─────────────────────────────┐
│ Agent 1: Drama Understanding │  ← 已完成
└─────────────┬───────────────┘
              │ report.json + action_plans + asr + assets
              ▼
┌─────────────────────────────┐
│ Agent 2: Interaction Design  │  ← 已完成
└─────────────┬───────────────┘
              │ ep_N.interactions.json (含集尾悬念)
              ▼
┌─────────────────────────────┐
│ Agent 3: Branch Narrative    │  ← 本文档
│ 消费全剧理解 + 最后几集细节    │
│ 产出: branch_narrative.json  │
└─────────────────────────────┘
```

### 4.2 输入

| 数据源 | 来自 | 用途 |
|--------|------|------|
| report.json | Agent 1 | 角色、伏笔、事件、关系 |
| episode_summaries (最后 2-3 集) | Agent 1 | 承接正片结尾的剧情细节 |
| plot_threads (status=open) | Agent 1 | 未解决的伏笔 → 分支的素材 |
| characters + personality | Agent 1 (SQLite/report) | 角色行为一致性 |
| assets/characters/*.jpg | Agent 1 | 角色参考图 → visual.reference_images |
| ep_N.interactions.json (最后一集) | Agent 2 | 集尾悬念 → 开场过渡的承接 |
| 全剧 ASR (最后 2 集) | ASR | 角色说话风格参考 |

### 4.3 内部流程

```
Phase 1: 世界观提取 + 路线规划
    输入: 全剧理解结果
    输出: 路线标签定义 + DAG 骨架 (节点 ID + 层级 + 汇合关系)
    
Phase 2: 逐节点内容生成
    输入: DAG 骨架 + 角色信息 + 剧情上下文
    输出: 每个节点的 narrative + choices
    
Phase 3: 视觉提示构造
    输入: 每个节点的 narrative + 角色参考图
    输出: 每个节点的 visual (prompt + reference_images + style_tags)
    
Phase 4: 一致性校验 + 组装
    输入: 全部节点
    输出: branch_narrative.json (最终数据包)
```

### 4.4 Phase 详解

#### Phase 1: 路线规划 (1 次 LLM 调用)

Prompt 给模型：
- 全剧角色列表 + 关系
- 未解决的伏笔 (open threads)
- 最后一集的剧情摘要和悬念
- 要求输出：
  - 3 条路线标签 (每条有名称 + 核心主题 + 情感走向)
  - 3 个结局概要
  - DAG 骨架 (每层几个节点，哪些节点汇合)
  - 开场过渡段（承接正片结尾）

输出 JSON:
```json
{
  "route_tags": [
    {"id": "justice", "name": "光明正道", "theme": "...", "emotion_arc": "..."},
    {"id": "shadow", "name": "暗影复仇", "theme": "...", "emotion_arc": "..."},
    {"id": "hermit", "name": "隐世归田", "theme": "...", "emotion_arc": "..."}
  ],
  "endings_outline": [...],
  "dag_skeleton": {
    "layers": [
      {"layer": 0, "nodes": ["n_opening"]},
      {"layer": 1, "nodes": ["n_l1_a", "n_l1_b"]},
      {"layer": 2, "nodes": ["n_l2_justice", "n_l2_shadow", "n_l2_hermit"]},
      {"layer": 3, "nodes": ["n_l3_a", "n_l3_b", "n_l3_c", "n_l3_d"]},
      {"layer": 4, "nodes": ["n_l4_justice", "n_l4_shadow", "n_l4_hermit"]}
    ],
    "edges": [
      {"from": "n_opening", "choices": [{"to": "n_l1_a"}, {"to": "n_l1_b"}]},
      {"from": "n_l1_a", "choices": [{"to": "n_l2_justice"}, {"to": "n_l2_shadow"}]},
      {"from": "n_l1_b", "choices": [{"to": "n_l2_shadow"}, {"to": "n_l2_hermit"}]},
      ...
    ]
  },
  "opening_narrative": "比武招亲大典落幕三日后..."
}
```

#### Phase 2: 逐节点生成 (N 次 LLM 调用，N=节点数)

对 DAG 中每个非结局节点，按拓扑顺序调用 LLM：
- 输入：本节点的路线标签、前驱节点的 narrative、本节点要连向的后继节点列表、角色信息
- 输出：narrative + choices

对结局节点单独调用（输入额外包含该路线的完整路径摘要）。

#### Phase 3: 视觉提示构造 (确定性逻辑 + 可选 LLM 辅助)

对每个节点：
1. 从 `characters_present` 查找 `assets/characters/` 下的参考图
2. 从 `scene_description` + `mood` 构造 Seedream prompt
3. 如果有 LLM 辅助：让模型基于 narrative 生成精确的画面描述

这步可以纯模板化，也可以用一次 LLM 精修 prompt。

#### Phase 4: 一致性校验 (确定性规则)

- DAG 连通性：从 entry_node 出发，所有路径最终到达某个 ending
- 死路检测：不存在没有 choices 且不是 ending 的节点
- 角色一致性：narrative 中出现的角色必须在 characters 列表中
- 选项对称性：同层节点的选项数量差 ≤ 1
- 汇合验证：标记为汇合的节点确实有 ≥2 条入边

---

## 5. 图片生成接口 (预留)

### 5.1 接口抽象

```python
# src/branch_narrative/image_generator.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class ImageRequest:
    prompt: str
    reference_images: list[Path]
    style_tags: list[str]
    size: str = "2K"
    node_id: str = ""

@dataclass
class ImageResult:
    node_id: str
    image_url: str | None = None      # Seedream 返回的 URL
    image_path: Path | None = None    # 本地保存路径
    prompt_used: str = ""
    status: str = "pending"           # pending | generated | skipped

class ImageGenerator(ABC):
    @abstractmethod
    def generate(self, request: ImageRequest) -> ImageResult: ...

class PlaceholderGenerator(ImageGenerator):
    """当前使用：不实际生图，只输出 prompt + 参考图路径"""
    def generate(self, request: ImageRequest) -> ImageResult:
        return ImageResult(
            node_id=request.node_id,
            prompt_used=request.prompt,
            status="skipped",
        )

class SeedreamGenerator(ImageGenerator):
    """未来接入：调用 Volcengine Seedream API"""
    def __init__(self, api_key: str, model: str = "doubao-seedream-4-5-251128"):
        self.api_key = api_key
        self.model = model
    
    def generate(self, request: ImageRequest) -> ImageResult:
        # POST https://ark.cn-beijing.volces.com/api/v3/images/generations
        # { "model": self.model, "prompt": request.prompt, "size": request.size }
        ...
```

### 5.2 配置

```env
# .env (未来)
BRANCH_IMAGE_GENERATOR=seedream          # placeholder | seedream
BRANCH_IMAGE_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3
BRANCH_IMAGE_MODEL=doubao-seedream-4-5-251128
BRANCH_IMAGE_TOKEN=xxx
```

当前默认 `BRANCH_IMAGE_GENERATOR=placeholder`。

---

## 6. 代码结构

```
src/branch_narrative/
├── __init__.py
├── agent.py                 # BranchNarrativeAgent.run() 主编排
├── phase1_planning.py       # 路线规划 + DAG 骨架
├── phase2_narrative.py      # 逐节点叙事生成
├── phase3_visual.py         # 视觉提示构造
├── phase4_validation.py     # DAG 一致性校验
├── context_builder.py       # 从 Agent 1/2 产物构建输入上下文
├── dag_types.py             # DAGNode, Choice, Ending 数据类型
├── image_generator.py       # 图片生成抽象 + Placeholder + Seedream
├── config.py                # BranchNarrativeConfig
└── output_writer.py         # 写出 branch_narrative.json
```

---

## 7. Prompt 设计要点

### 7.1 Phase 1 Prompt 核心指令

```
你是一位短剧编剧，擅长设计分支叙事。

现在你需要为一部已完结的短剧设计"观众选择驱动的后续剧情"。

## 输入
- 全剧角色、关系、伏笔
- 最后一集的剧情和悬念
- 规格要求：3条路线、3个结局、4-5层选择、总节点≤25

## 你需要输出
1. 三条路线的定义（标签、主题、情感弧线）
2. 三个结局的概要（如何收束、角色命运）
3. DAG 骨架（每层的节点 ID + 边 + 哪些节点是汇合节点）
4. 开场过渡叙事（承接正片最后一集结尾）

## 约束
- 路线之间要有情感差异（不是好/中/坏，而是不同价值观选择）
- 汇合节点的叙事要能兼容多条入边（不能只承接一条路径的逻辑）
- 每个选项要让用户感到"两个都想选"（不能有明显的正确答案）
- 角色行为要符合正片中已建立的性格
```

### 7.2 Phase 2 每节点 Prompt 核心指令

```
你正在为分支剧情的一个节点撰写内容。

## 上下文
- 本节点 ID: {node_id}
- 所属路线: {route_tag}
- 前驱节点叙事摘要: {predecessor_summary}
- 后继节点列表: {successors} (你的选项要导向这些节点)
- 本节点涉及角色: {characters}
- 角色性格参考: {character_profiles}
- 角色对话风格参考 (ASR): {dialogue_samples}

## 输出要求
1. narrative: 2-4 段叙事文本 (300-600字)
2. choices: 为每个后继节点写一个选项文本 + 选项副文本
3. scene_description: 一句话描述画面
4. mood: 一个情绪词

## 约束
- 如果本节点是汇合节点（有多条入边），叙事不能假设用户从特定路径来
- 选项文本要简洁有力（≤15字），副文本补充后果暗示（≤25字）
- 叙事中角色的对话要符合正片中的说话风格
```

---

## 8. CLI 接入

```bash
drama-agent branch-narrative \
  --project projects/test-5eps-v2 \
  --output-dir outputs \
  --drama-id example-drama-a \
  --image-mode placeholder           # placeholder | seedream
```

产出：
```
outputs/example-drama-a/branch_narrative.json
outputs/example-drama-a/branch_images/       # 未来 seedream 模式下的图片
```

---

## 9. 前端消费方式

前端逻辑极简：

```javascript
// 伪代码
let currentNode = data.entry_node;

function render(nodeId) {
  const node = data.nodes[nodeId];
  showNarrative(node.narrative);
  showImage(node.visual);  // 或 placeholder
  showChoices(node.choices);
}

function onChoice(choice) {
  currentNode = choice.leads_to;
  if (currentNode in data.endings) {
    renderEnding(data.endings[currentNode]);
  } else {
    render(currentNode);
  }
}
```

不需要状态计算、标签累加或复杂路由——DAG 已经是展平的确定性图。

---

## 10. 与现有系统的耦合点

| 耦合 | 具体位置 | 方式 |
|------|---------|------|
| 读取 report.json | context_builder.py | 与 interaction_designer 相同 |
| 读取 assets/characters/ | phase3_visual.py | 直接读目录 |
| 读取最后一集 interaction manifest | context_builder.py | 取 episode_end_interaction |
| LLM 调用 | agent.py | 复用 DoubaoClient._chat (文本模式) |
| CLI 注册 | drama_agent/cli.py | 新增 branch-narrative 命令 |

**不需要修改 Agent 1 或 Agent 2 的任何代码。**

---

## 11. 限制与风险

| 项 | 说明 | 缓解 |
|----|------|------|
| 汇合节点叙事质量 | 需要兼容多条入边，可能显得模糊 | Prompt 明确要求"不假设特定前序路径" |
| 角色一致性 | LLM 可能让角色做出正片中不会做的事 | 注入角色性格 + 对话风格样本 |
| 节点数量控制 | LLM 可能输出超过 25 个节点的 DAG | Phase 4 硬规则裁剪 |
| 图片一致性 | 不同节点的同一角色视觉应一致 | 始终使用同一张 reference_image |
| 选项吸引力均衡 | 可能出现"一眼正确答案" | Prompt 强调"两个都想选" |

---

## 12. 执行计划

```
Phase A: 骨架搭建 (dag_types + config + context_builder + output_writer)
Phase B: Phase 1 路线规划 (planning prompt + LLM 调用 + JSON 解析)
Phase C: Phase 2 逐节点生成 (narrative prompt + 拓扑排序遍历)
Phase D: Phase 3 视觉提示 (reference 查找 + prompt 构造 + placeholder)
Phase E: Phase 4 校验 + CLI 接入 + 端到端测试
```

---

## 13. 依赖

无新外部依赖。复用现有的：
- httpx (LLM 调用)
- pydantic (数据类型)
- json-repair (LLM JSON 容错)
- typer / rich (CLI)
