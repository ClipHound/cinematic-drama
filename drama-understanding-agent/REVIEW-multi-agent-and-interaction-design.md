# 审核评估报告：多 Agent 实现与交互设计 Agent 产出

> 审核日期: 2026-06-10
> 审核范围: `drama-understanding-agent` 完整项目
> 审核焦点: (1) 多 Agent 实现情况 (2) Interaction Design Agent 产出质量

---

## 一、项目概况

`drama-understanding-agent` 是一个短剧理解与互动设计系统，由两个子系统组成：

| 子系统 | 代码路径 | 代码量 |
|--------|---------|--------|
| drama-understanding-agent (理解 Agent) | `src/drama_agent/` | ~1800 行，20+ 文件 |
| interaction-design-agent (互动设计 Agent) | `src/interaction_designer/` | ~500 行，10 文件 |
| interaction-generator (规则转换器，降级保留) | `src/interaction_generator/` | ~250 行，5 文件 |

设计文档 12 份 (`docs/`)，测试文件 14 份 (33 个测试函数，全部通过)。

---

## 二、多 Agent 实现评估

### 2.1 架构形态

系统采用**串行双阶段流水线**架构：

```
全部视频 + ASR
    │
    ▼
┌─────────────────────────────┐
│ Agent 1: Drama Understanding │  ← 逐集循环 (VLM 理解 → Action Plan → Memory)
│ 产出: report.json            │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Agent 2: Interaction Design  │  ← Pass 1 (全局) → Pass 2 (逐集)
│ 产出: ep_N.interactions.json │
└─────────────────────────────┘
```

Agent 1 完成后 Agent 2 才启动。Agent 2 不看视频，只消费 Agent 1 的结构化产出（`report.json` + `action_plans/` + `asr/`）。

### 2.2 Agent 定义对照

按照设计文档 `INTERACTION-DESIGN-AGENT-BRIEF.md` 中对 "Agent" 的定义标准（固定职责边界、自主决策过程、结构化输入→结构化输出、有执行编排和质量控制），逐项对照：

| 标准 | Agent 1 (理解) | Agent 2 (互动设计) |
|------|:---:|:---:|
| 固定职责边界 | ✅ | ✅ |
| 自主决策过程 | ✅ VLM 自主输出 Action Plan | ✅ LLM 自主选组件、调时间、定密度 |
| 结构化输入→输出 | ✅ 视频+ASR→Action Plan JSON | ✅ report.json→interaction_points JSON |
| 执行编排 | ✅ EpisodeLoop 逐集迭代 | ✅ Pass1→Pass2 两阶段编排 |
| 质量控制 | ✅ PatchCommitter + 置信度阈值 | ✅ safety_rules 硬规则后处理 |

两个子系统在设计意图上符合项目自身定义的 Agent 标准。

### 2.3 Agent 间关系

- **协作方式**：串行生产者-消费者。Agent 1 产出，Agent 2 消费。Agent 2 不向 Agent 1 反馈。
- **信息传递**：通过文件系统（`report.json`、`action_plans/ep_N.json`、`asr/ep_N.json`）。
- **无交互机制**：Agent 2 无法要求 Agent 1 重新处理某集；Agent 1 不知道 Agent 2 如何使用其产出。
- **无对抗验证**：不存在第三个 Agent 或验证步骤来审核 Agent 2 的产出质量。
- **无模型多样性**：两个 Agent 共用同一个 Doubao 模型，仅 temperature 不同（Agent 2 用 0.2）。

### 2.4 Agent 1 内部的 Agent 特征

Agent 1 (`EpisodeLoop`) 内部有类 Agent 循环：
- 感知：VLM 看视频 + ASR 文本
- 决策：VLM 输出 Action Plan JSON（包含要执行的 action 类型和参数）
- 执行：`ActionPlanEngine` 解析 JSON → 分发到 7 种 handler → 生成 StatePatch
- 记忆：`PatchCommitter` 将 patch 事务性提交到 SQLite + Qdrant
- 迭代：逐集循环，每集积累记忆后影响下一集的上下文构建

这是系统中 Agent 特征最明显的部分。

### 2.5 Agent 2 内部的 Agent 特征

Agent 2 (`InteractionDesignAgent`) 内部：
- 两个顺序 LLM 调用（Pass 1 全局建模 + Pass 2 逐集设计）
- 无迭代循环（不像 Agent 1 那样逐集积累状态）
- 无工具调用（不调用外部函数，纯文本→JSON）
- 安全规则是确定性后处理，不涉及 LLM 判断
- 每次 LLM 调用是一次性 prompt→response，不涉及多轮推理

Agent 2 在结构上更接近"带安全后处理的 LLM 批处理管道"，而非传统意义上的自主 Agent。

---

## 三、Interaction Design Agent 产出质量评估

### 3.1 评估依据

以 `docs/09-interaction-design-agent-sdd.md` 为规格基线，以 `outputs/v3-default/example-drama-a/` 的 5 集实际产出为评估样本，逐字段、逐规则对照。

### 3.2 结构完整性

对照 SDD §4.4.2 定义的输出 JSON Schema：

| 字段 | 要求 | 实际 | 状态 |
|------|------|------|:---:|
| `interaction_points[].id` | `ip_ep_NNN_NNNN` 格式 | 符合 | ✅ |
| `interaction_points[].start_ms` | 毫秒整数 | 符合 | ✅ |
| `interaction_points[].end_ms` | 毫秒整数，> start_ms | 符合 | ✅ |
| `interaction_points[].component` | 从组件库选择 | 全部在 ALLOWED_COMPONENTS 内 | ✅ |
| `interaction_points[].emotion` | 观众情绪 | 已填充 | ✅ |
| `interaction_points[].intensity` | 0.0-1.0 | 已填充，范围合规 | ✅ |
| `interaction_points[].priority` | 0.0-1.0 | 已填充，范围合规 | ✅ |
| `interaction_points[].confidence` | 0.0-1.0 | 已填充，范围合规 | ✅ |
| `interaction_points[].title` | 审核可读标题 | 已填充，中文描述清晰 | ✅ |
| `interaction_points[].key_line` | 代表性台词 | 已填充 | ✅ |
| `interaction_points[].key_visual` | 关键画面描述 | 已填充 | ✅ |
| `interaction_points[].highlight_reason` | 互动理由 | 已填充，有叙事依据 | ✅ |
| `interaction_points[].score_type` | resonance\|guard\|insight\|cocreate | **出现 `"support"` 值** | ⚠️ |
| `interaction_points[].config` | 组件配置对象 | **5 集全部 23 个点均为 `{}`** | ⚠️ |
| `episode_end_interaction` | predictions/voices/clue_summary | 已填充 | ✅ |
| `design_notes` | 设计思路说明 | 已填充 | ✅ |

### 3.3 安全规则合规性

对照 SDD §4.6 和 `safety_rules.py` 实际实现的规则：

| 规则 | 要求 | 5 集实测 | 状态 |
|------|------|---------|:---:|
| G1 时长约束 | 每个点 5000-20000ms | 全部合规 | ✅ |
| G4 重叠检测 | 相邻点间隔 ≥ 10000ms | 全部合规 | ✅ |
| G6 数量上限 | 按密度配置动态计算 | 全部合规 | ✅ |
| G8 覆盖率上限 | 总互动时长 ≤ 35% 剧集时长 | 全部合规 | ✅ |
| G7 组件多样性 | ≥3 个点时至少 2 种组件 | 全部合规 | ✅ |
| G9 预测题可验证 | answer_key 校验 | **代码中未实现此规则** | ⚠️ |
| 边界偏移 | 接近片尾的点自动偏移 | ep_003 触发 1 次修复 | ✅ |
| 组件白名单 | 非法组件移除 | 无触发 | ✅ |

5 集输出的 `design_warnings` 均为空数组。ep_003 有 1 条 `design_repairs`（边界偏移），修复后合规。

### 3.4 情绪-场景-组件匹配度

以 v3-default 的 5 集 23 个互动点为样本，评估情绪判断与组件选择的合理性：

**第 1 集（铺垫集，中等密度）** — 5 个点：
```
43000ms  team_cheer      ← 朝堂焦虑，为示例王朝助威          [合理：站队场景]
84000ms  laugh_burst     ← 纨绔撒钱反差笑点              [合理：喜剧场景]
170000ms anger_release   ← 皇帝怒斥败家纨绔              [合理：愤怒共鸣]
245000ms anger_release   ← 蛮夷嚣张辱国                  [合理：愤怒升级]
282000ms shatter_strike  ← 神秘高手隔空打脸              [合理：爽感释放]
```
情绪曲线：焦虑→笑点→愤怒→愤怒升级→爽感释放。符合"铺垫集建立 stakes + 结尾钩子"的定位。

**第 3 集（情感集，中等密度）** — 4 个点：
```
30000ms  anger_release   ← 被恶意针对的不公              [合理]
107000ms team_cheer      ← 站队觉醒主角                  [合理：支持场景]
138000ms clue_judge_card ← 毒杀真相揭晓                  [合理：线索闭环]
155000ms tear_resonance  ← 共情十五年隐忍                [合理：泪点]
```
情绪曲线：愤怒→支持→洞察→共情。与蓝图"压抑隐忍→复仇决绝"的定位一致。

**第 5 集（高燃集，高密度）** — 4 个点 (v2-default)：
```
laugh_burst → tear_resonance → anger_release → shatter_strike
```
以 shatter_strike 收尾，符合高燃集的定位。

23 个互动点中没有发现情绪与组件明显不匹配的情况。悲伤场景未出现 shatter_strike/celebrate_confetti，甜蜜场景未出现 anger_release。

### 3.5 rhythm_blueprint 质量

Pass 1 产出的全局节奏蓝图：
- 剧集类型判断：5 集分别定位为铺垫→过渡→情感→铺垫→高燃，没有连续两集同类型
- 密度分配：中→低→中→中→高，呈现渐强趋势
- 集尾互动类型：prediction → clue_review → character_voice → prediction → prediction，类型有变化
- `escalation_plan` 描述了"逐集阶梯式上升"的互动爽感递增策略

5 集短剧场景下蓝图的合理性高。

### 3.6 发现的问题

**问题 A：`score_type` 字段值越界**

SDD §4.4.2 定义 `score_type` 为 `resonance|guard|insight|cocreate`。实际输出中，ep_003 的一个 `team_cheer` 点的 `score_type` 为 `"support"`（v3-default）或 `"guard"`（v3-rerun），ep_001 的 `team_cheer` 点（v3-default）为 `"support"`。`"support"` 不在 SDD 定义的枚举中。`safety_rules.py` 未对此字段做白名单校验。

**问题 B：`config` 字段全局空置**

SDD §4.5 组件库说明书定义了多个组件需要特殊配置：
- `team_cheer` 需要 `team_options`（两个阵营）
- `prediction_card` 需要 `question + options`
- `clue_judge_card` 需要 `question + options`

但 23 个互动点的 `config` 全部为 `{}`。这些配置信息实际上被放在了 `episode_end_interaction.predictions[]` 中（不属于任何具体 interaction_point），而非填入对应 interaction_point 的 `config` 字段。

**问题 C：design_notes 与实际数据不一致**

ep_004（v2-default）的 `design_notes` 写道"共 6 个互动点"，但 manifest 实际包含 5 个点。LLM 在生成说明文本时自己数错了。

**问题 D：多次运行结果存在差异**

v3-default 与 v3-rerun 对 ep_001 同一时段的同一场景选择了不同组件：
- v3-default: `team_cheer`（站队助威）
- v3-rerun: `guardian_shield`（守护加持）

两种选择在各自语境下都合理，但说明 LLM 的选择有一定随机性。系统没有机制确保关键互动点的组件选择在多次运行间一致。

**问题 E：G9 规则未实现**

SDD §4.6.2 定义了 G9 规则（"prediction missing answer_key"），`safety_rules.py` 中未实现此校验。

### 3.7 与 SDD 的对齐度

| SDD 章节 | 对齐 |
|----------|:---:|
| §4.3 Pass 1 全剧建模 | ✅ |
| §4.4 Pass 2 逐集设计 | ✅ |
| §4.5 组件库说明书 (12 组件) | ✅ |
| §4.6 安全自检规则 (G1/G4/G6/G7/G8) | ✅ |
| §4.6 安全自检规则 (G9) | ❌ 未实现 |
| §6.1 CLI (`full-pipeline` + `design-interactions`) | ✅ |
| §6.2 full-pipeline 流程编排 | ✅ |

SDD 到代码的对齐率：6/7 章节完全对齐，1 项规则缺失。

---

## 四、测试覆盖

### 4.1 整体测试

- 14 个测试文件，33 个测试函数，全部通过
- 覆盖：memory store、action plan 解析、action handlers、state patch、episode loop、project、doubao client、vectors、relationship dedup、thread dedup、table validation、report markdown、ASR client、interaction designer agent

### 4.2 Interaction Design Agent 专项测试

`tests/test_interaction_designer_agent.py` 包含 3 个测试：

| 测试 | 类型 | 状态 |
|------|------|:---:|
| `test_interaction_design_agent_uses_llm_design_output` | 集成测试 (FakeLLM) | ✅ |
| `test_safety_rules_shift_boundary_point_to_valid_duration` | 边界偏移逻辑 | ✅ |
| `test_safety_rules_trim_short_episode_by_density` | 密度截断逻辑 | ✅ |

缺少的测试类型：
- Pass 1 蓝图解析异常输入测试
- Pass 2 JSON 解析异常输入测试
- 完整 manifest 结构字段合规性测试
- score_type 白名单校验测试
- config 字段非空测试（当组件需要配置时）

### 4.3 端到端测试

`docs/TEST-REPORT-fullpipeline-5eps.md` 记录了 5 集完整流程测试：
- Phase 1 (理解): 638.5 秒，产出 15 角色/3 关系/16 事件/2 伏笔/25 候选互动点
- Phase 2 (设计): 223.9 秒，产出 5 个 interaction manifest
- 结果: 5 个 manifest 均 0 warnings、0 repairs（ep_003 1 repair 已被自动修复）
- 结论: pass with notes，无阻塞性问题

---

## 五、与设计文档定位的一致性

`INTERACTION-DESIGN-AGENT-BRIEF.md` 对 Agent 的定位论证：

> "固定责任边界、自主决策过程、结构化输入→输出、有执行编排与质量控制"

两个子系统均满足这四条标准。但 Agent 2 的"自主决策"体现为单次 LLM 调用的 prompt→response，而非持续的环境感知→决策→行动循环。

`docs/09-interaction-design-agent-sdd.md` 对系统间关系的定义：

> "两个 Agent 是协作关系，不是主从关系"

实际实现中是串行生产者-消费者关系，无双向协作。Agent 2 依赖 Agent 1 的产出，Agent 1 不感知 Agent 2 的存在。

---

## 六、汇总

| 维度 | 结论 |
|------|------|
| 多 Agent 架构形态 | 串行双阶段流水线。Agent 1 内部有完整的感知→决策→执行→记忆循环；Agent 2 内部是两个顺序 LLM 调用加上确定性安全后处理。两个 Agent 之间无反馈、无协商、无对抗验证。 |
| Agent 1 与设计对齐 | 6 条架构原则全部落地，7 种 Action type 全部实现，11 张 SQLite 表 + 3 个 Qdrant Collection 全部创建。V2 修复了 7 个数据完整性 bug。对齐度 96/100（来源：自评审核报告 `07-alignment-audit.md`）。 |
| Agent 2 与设计对齐 | SDD 定义的功能 6/7 对齐。G9 规则未实现。产出结构完整，前端可消费。 |
| Interaction Design 产出质量 | 情绪判断与组件选择在 23 个采样点中无不匹配。安全规则全部通过（5 集 0 warnings）。3 个问题：score_type 偶有越界值、config 字段全局空置、LLM 自述文本偶有计数偏差。 |
| 可复现性 | 同一输入多次运行产出合理但存在差异（组件选择不同）。系统未对关键点的一致性做约束。 |
| 测试 | 33 个单元测试全部通过。Interaction designer 专项测试 3 个，覆盖核心路径但未覆盖异常输入和字段合规性。 |
