# Interaction Design Agent 简要说明

## 1. 它负责什么

`interaction-design-agent` 是全剧理解完成后进入的“互动导演”。它不重新看视频，而是消费 `drama-understanding-agent` 已经产出的结构化结果，包括：

- 每集摘要、情绪、悬念
- 角色、关系、伏笔、剧情事件
- ASR 时间戳结果
- `candidate_interactions[]` 候选互动点

它的目标不是聊天回答问题，而是产出前端可以直接消费的 `Episode Interaction Manifest`：

```text
outputs/{drama_id}/ep_001.interactions.json
outputs/{drama_id}/ep_002.interactions.json
...
```

每个 manifest 包含最终的 `interaction_points[]`，字段对齐 `OFFLINE_VIDEO_UNDERSTANDING_OUTPUT_SPEC.md`，例如 `start_ms`、`end_ms`、`component`、`emotion`、`confidence`、`config`。

## 2. 它怎么工作

当前实现是一个同步、两阶段的设计 agent。

### Pass 1: 全剧互动节奏规划

读取全剧上下文，生成 `rhythm_blueprint`：

- 每集定位：铺垫集、过渡集、高燃集、情感集、反转集
- 每集互动密度：low、medium、high
- 每集主情绪和设计重点
- 集尾互动策略

对应实现：

- `src/interaction_designer/agent.py`
- `src/interaction_designer/pass1_global.py`
- `src/interaction_designer/context_builder.py`

### Pass 2: 逐集互动设计

对每集读取：

- 本集 `candidate_interactions`
- 本集 ASR
- 本集 plot events
- Pass 1 给出的本集节奏蓝图
- 组件库说明
- 安全规则

然后由 LLM 自主决定：

- 哪些候选点保留
- 每个点用哪个前端组件
- 时间窗口是否微调
- 互动强度、优先级、审核理由
- 集尾预测/角色心声/线索回顾

对应实现：

- `src/interaction_designer/pass2_episode.py`
- `src/interaction_designer/component_library.py`

### Safety Post-processing

LLM 输出后不是直接下发，而是进入硬规则后处理：

- 过滤非法组件
- 修正片尾越界点
- 保证互动时长在 5-20 秒
- 移除或替换重叠互动
- 限制最大数量
- 输出 `design_warnings` 和 `design_repairs`

对应实现：

- `src/interaction_designer/safety_rules.py`
- `src/interaction_designer/output_formatter.py`

## 3. 为什么它是 agent，而不是 chatbot

它不是 chatbot，原因有四点。

第一，它有固定职责和边界。

Chatbot 的核心是和用户多轮对话，回答用户问题。这里的 agent 没有用户聊天入口，也不生成自然语言答复给用户。它只执行“根据剧情理解结果设计前端互动方案”这个明确任务。

第二，它有自主决策过程。

它不是把情绪标签简单映射成组件。Pass 2 prompt 明确要求“自主判断，而不是机械映射”，模型需要在剧情语境、候选点、全局节奏、组件库之间做选择。例如同样是紧张场景，可能选择 `guardian_shield`、`prediction_card` 或 `emotion_buffer`，取决于当集位置和观众情绪。

第三，它有结构化输入、结构化输出和可验证副作用。

输入不是用户随口提问，而是完整工程上下文：

```text
report.json + action_plans + asr + component library + rhythm_blueprint
```

输出也不是聊天文本，而是稳定 JSON artifact：

```text
ep_001.interactions.json
ep_002.interactions.json
...
```

这些文件能被后端/前端直接消费，也能被测试脚本验证。

第四，它有执行编排和质量控制。

`InteractionDesignAgent.run()` 会自动完成：

```text
加载项目上下文
-> 全剧 Pass 1 规划
-> 遍历每集 Pass 2 设计
-> safety_rules 后处理
-> 写出 manifest
-> 返回 DesignResult
```

这是一段可重复执行的任务流程，不是一次自由聊天。

## 4. 它是不是“完整 Agent Loop”

严格说，它不是 AutoGPT 那种无限循环 agent，也没有开放式 tool calling loop。SDD-09 明确选择了“同步、无 Agent Loop”的实现。

所以更准确的定义是：

```text
它是一个任务型 LLM Agent / Workflow Agent，
不是通用自主代理，
也不是 chatbot。
```

它的 agent 性体现在：

- 有明确角色：互动导演
- 有任务目标：生成互动 manifest
- 有上下文感知：消费全剧结构化理解结果
- 有自主决策：选择互动点和组件
- 有执行流程：Pass 1 + Pass 2 + 后处理 + 写文件
- 有可验证产物：前端可消费 JSON

## 5. 如何证明

可以用三类证据证明。

### 代码证据

- `InteractionDesignAgent.run()` 编排完整流程，不是对话入口。
- `pass1_global.py` 生成全剧节奏蓝图。
- `pass2_episode.py` 生成逐集互动设计。
- `context_builder.py` 从工程产物构建上下文。
- `safety_rules.py` 对 LLM 结果做工程约束和修正。
- CLI 命令 `design-interactions` 能无人工对话地批量生成结果。

### 产物证据

运行后生成：

```text
outputs/example-drama-a/ep_001.interactions.json
outputs/example-drama-a/ep_002.interactions.json
outputs/example-drama-a/ep_003.interactions.json
outputs/example-drama-a/ep_004.interactions.json
outputs/example-drama-a/ep_005.interactions.json
```

这些文件包含可播放页消费的 `interaction_points[]`，不是聊天回复。

### 行为证据

同一份输入工程数据，多次运行会执行同一条任务链：

```text
全剧建模 -> 单集设计 -> 安全修正 -> manifest 写出
```

这说明它是自动化任务执行单元。chatbot 不会自然地产生这种稳定的工程副作用和可验证产物。

## 6. 当前限制

- 当前是同步 workflow agent，不是多轮自我反思 agent。
- Pass 1 蓝图目前没有单独持久化，只体现在后续逐集设计上下文中。
- `design_notes` 是 LLM 生成的解释文本，可能与 safety 后处理后的最终点数略有不一致；最终可信对象应以 manifest 的 `interaction_points[]` 和 `design_warnings` 为准。
- 质量依赖上游 `candidate_interactions` 和 ASR 时间戳质量。

## 7. 简短结论

`interaction-design-agent` 是一个任务型互动设计 agent。它不是 chatbot，因为它不做开放对话，而是读取结构化剧情理解结果，经过全剧规划、逐集自主设计和安全后处理，产出可验证、可消费、可落盘的前端互动 manifest。
