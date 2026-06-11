# 审核评估报告：Branch Narrative Agent 实现与产出

> 审核日期: 2026-06-10
> 审核依据: `docs/12-branch-narrative-agent-sdd.md` (SDD)
> 审核范围: `src/branch_narrative/` 全部代码 + `outputs/example-drama-a-20eps-final/example-drama-a/branch_narrative.json` + `tests/test_branch_narrative_agent.py`

---

## 一、代码实现与 SDD 对齐

### 1.1 模块清单

SDD §6 定义了 9 个模块文件，实际实现了 10 个：

| SDD 定义 | 实际文件 | 状态 | 行数 |
|----------|---------|:---:|------|
| `agent.py` (主编排) | `agent.py` | ✅ | ~90 |
| `phase1_planning.py` | `phase1_planning.py` | ✅ | ~150 |
| `phase2_narrative.py` | `phase2_narrative.py` | ✅ | ~200 |
| `phase3_visual.py` | `phase3_visual.py` | ✅ | ~80 |
| `phase4_validation.py` | `phase4_validation.py` | ✅ | ~80 |
| `context_builder.py` | `context_builder.py` | ✅ | ~140 |
| `dag_types.py` | `dag_types.py` | ✅ | ~70 |
| `image_generator.py` | `image_generator.py` | ✅ | ~60 |
| `config.py` | `config.py` | ✅ | ~20 |
| `output_writer.py` | `output_writer.py` | ✅ | ~15 |
| (SDD 未定义) | `__init__.py` | ✅ | 1 |

所有 SDD 定义的模块均已实现，无遗漏。所有文件均未超过 300 行。

### 1.2 数据模型对齐

SDD §3 定义的三种核心数据结构：

| SDD 结构 | 代码实现 | 字段完备度 |
|----------|---------|:---:|
| `BranchNode` (§3.2) | `dag_types.py:BranchNode` | 100% — node_id, layer, route_tag, narrative*, visual*, choices[], audio_hint* 全部实现 |
| `Choice` (§3.2) | `dag_types.py:Choice` | 100% — choice_id, option_text, option_subtext, leads_to 全部实现 |
| `BranchEnding` (§3.3) | `dag_types.py:BranchEnding` | 100% — ending_id, ending_title, ending_subtitle, narrative*, visual*, epilogue, character_fates 全部实现 |
| `BranchNarrativeConfig` (§2.3) | `config.py:BranchNarrativeConfig` | 100% — max_nodes=25, route_count=3, min/max_choices=2/3, target_choice_depth=4, image_mode="placeholder", version="1.0" |

### 1.3 四阶段流程对齐

SDD §4.3 定义的四阶段流程：

| 阶段 | SDD 描述 | 代码实现 | 对齐 |
|------|---------|---------|:---:|
| Phase 1 | 路线规划 (1 次 LLM) | `run_planning()` → 输出 route_tags + endings_outline + dag_skeleton + opening_narrative | ✅ |
| Phase 2 | 逐节点内容生成 (N 次 LLM) | `generate_nodes()` + `generate_endings()` → 拓扑排序顺序生成 | ✅ |
| Phase 3 | 视觉提示构造 | `attach_visuals()` → 为每节点生成 visual 字段，`PlaceholderGenerator` 返回 skipped | ✅ |
| Phase 4 | 一致性校验 | `validate_package()` → G1-G7 检查，返回 warnings | ✅ |

Phase 1 fallback 机制：`normalize_plan()` 无法验证的 plan 会 fallback 到 `_fallback_plan()`（硬编码 DAG 骨架），保证系统不会因 LLM 输出异常而崩溃。

### 1.4 CLI 与集成

SDD §8 定义的 CLI 命令：

```bash
drama-agent branch-narrative \
  --project projects/test-5eps-v2 \
  --output-dir outputs \
  --drama-id example-drama-a \
  --image-mode placeholder
```

`cli.py:148-177` 完整实现了此命令，额外增加 `--interactions-dir` 参数。

### 1.5 图片生成接口

SDD §5 定义的 `PlaceholderGenerator` 和 `SeedreamGenerator` 均已实现。`PlaceholderGenerator` 总是返回 `status="skipped"`。`SeedreamGenerator.generate()` 抛出 `NotImplementedError`，符合"接口预留"的定位。

---

## 二、20 集产出结构分析

### 2.1 整体规格

| 指标 | SDD 目标 | 实际产出 | 合规 |
|------|---------|---------|:---:|
| 总节点数 | ≤25 | 16 (13 内容 + 3 结局) | ✅ |
| 结局数 | 3 | 3 | ✅ |
| 路线数 | 3 | 3 (天下为公/法理昭昭/快意逍遥) | ✅ |
| 选择层数 | 4-5 | 5 层 (Layer 0-4) | ✅ |
| 图片状态 | placeholder | 全部 skipped | ✅ (预期) |
| 连通性 (entry→ending) | 全部可达 | 全部可达 | ✅ |
| 死路 | 0 | 0 | ✅ |
| warnings | — | [] | ✅ |

### 2.2 路线设计质量

三条路线的标签定义：

| 路线 | 名称 | 核心主题 | 情感弧线 |
|------|------|---------|---------|
| `public_good` | 天下为公 | 私仇让位于家国大义 | 武者→护国英雄 |
| `law_retribution` | 法理昭昭 | 依律裁决不徇私 | 冲动复仇→法理贤臣 |
| `free_will` | 快意逍遥 | 拒绝皇权绑定 | 隐忍→自由 |

三条路线在价值观上有本质差异（家国责任 vs 规则公正 vs 个人自由），符合 SDD §7.1 "不是好/中/坏，而是不同价值观选择" 的要求。

### 2.3 DAG 结构分析

#### Layer 结构：

```
Layer 0: n_opening       (1 节点, 3 个分叉选项 → 通向 3 条路线)
Layer 1: n_l1_1/2/3     (3 节点, 各 2 个选项)
Layer 2: n_l2_public/law/free  (3 节点, 各 2 个选项)
Layer 3: n_l3_public/law/free  (3 节点, 各 2 个选项)
Layer 4: n_l4_public/law/free  (3 节点, 各 1 个选项 → 结局)
```

#### 选择分叉度分析（关键发现）：

| 节点 | 选项数 | 指向不同节点数 | 真分叉 |
|------|--------|:---:|:---:|
| n_opening | 3 | 3 | ✅ |
| n_l1_1 | 2 | 1 (全到 n_l2_public) | ❌ |
| n_l1_2 | 2 | 1 (全到 n_l2_law) | ❌ |
| n_l1_3 | 2 | 1 (全到 n_l2_free) | ❌ |
| n_l2_public/law/free | 2 | 1 | ❌ |
| n_l3_public/law/free | 2 | 1 | ❌ |
| n_l4_public/law/free | 1 | 1 | ❌ |

**13 个节点中仅 1 个 (n_opening) 存在真正的选择分叉。**

#### 跨路线合并分析：

SDD §2.4 DAG 示意图明确描述了跨路线汇合模式：

```
N1a "选择B" → N2b ← N1b "选择A"
```

实际产出中：**0 处跨路线合并**。所有 "汇合节点" 的入边均来自同一父节点（单个父节点的多个选项指向同一个子节点），而非来自不同路线的不同父节点。

#### 实际路径（3 条完全独立的线性路径）：

```
Path A: n_opening → n_l1_1 → n_l2_public → n_l3_public → n_l4_public → ending_guardian (镇国柱石)
Path B: n_opening → n_l1_2 → n_l2_law → n_l3_law → n_l4_law → ending_justice (律法如秤)
Path C: n_opening → n_l1_3 → n_l2_free → n_l3_free → n_l4_free → ending_roamer (江湖逍遥)
```

用户在**第一个选择点**后，后续所有 4 次选择均不影响路径——无论选什么，都走到同一个下一节点。**实际有效选择深度 = 1，而非 SDD 规定的 4-5。**

### 2.4 叙事质量

开场过渡段 (n_opening) 的 prose 质量：

```
"鎏金雅间内明黄御座旁，君主B笑着拍了拍角色X的肩，满殿跪着的苏家人早已抖成筛子。反派C眼底满是绝望，角色X攥紧的拳骨节泛白，压了十五年的杀母之仇近在眼前..."

"角色X指尖拂过腰间母亲留下的旧玉佩，十五年伪装纨绔的隐忍、擂台之上护国的热血、此刻近在咫尺的仇人，所有情绪在胸腔里翻涌..."
```

- 承接了正片"比武招亲落幕、角色X身份暴露、反派C阴谋浮出水面"的结尾状态
- 角色行为与正片建立的人格一致 (角色X隐忍/君主B重情)
- 每段 narrative 包含 2-4 段，每段 80-180 字，符合 300-600 字总量要求
- 三个结局差异化明显：武将路线 (镇国柱石)、文臣路线 (律法如秤)、侠客路线 (江湖逍遥)

### 2.5 选项质量

| 特征 | 表现 |
|------|------|
| option_text 长度 | 6-14 字，简洁有力 |
| option_subtext 长度 | 8-18 字，提供后果暗示 |
| 选项间区分度 | n_opening 的 3 个选项差异化好 (领兵/持牌/手刃) |
| 后续节点选项区分度 | 有明显的问题是：n_l2_free 的 option_subtext 为 "选择不同的命运方向"，过于模糊 |
| "两个都想选" 标准(SDD §7.1) | n_opening 勉强达到；后续节点选项因无实际后果差异，选择动机薄弱 |

---

## 三、校验系统实际表现

Phase 4 (`phase4_validation.py`) 实现了 7 条校验规则：

| 规则 | 含义 | 20 集产出 | 备注 |
|------|------|:---:|------|
| G1 | entry_node 缺失 | ✅ 通过 | n_opening 存在 |
| G2 | 总节点超限 | ✅ 通过 | 16/25 |
| G3/G4 | 死路检测 | ✅ 通过 | 无孤儿节点 |
| G5/G6 | 可达性 | ✅ 通过 | BFS 覆盖全部 |
| G7 | 汇合验证 (≥1 节点 indegree≥2) | ✅ 通过 | 但通过的是"伪汇合"（单一父节点多选项指向同一子节点），非跨路线汇合 |

**G7 校验的通过条件不足以区分"真正的跨路线 DAG 汇合"与"单路线内选项收束"**。当前 9 个节点 indegree≥2 全部属于后者。

---

## 四、测试与运行结果

### 4.1 测试

- 总测试数：38 passed
- 分支剧情专项测试：1 个 (`test_branch_narrative_agent_writes_package`)
- 测试覆盖：FakeLLM → fallback plan → 包写出 → 结构验证
- 测试未覆盖：真实 LLM 输出解析、Plan normalize 边界情况、merge 质量校验

### 4.2 代码规模

- `src/branch_narrative/`：11 文件，总计约 900 行
- 所有文件 ≤ 200 行（符合"不超 300 行"的约束）

---

## 五、与 SDD 关键设计的偏差

| SDD 要求 | 实际产出 | 偏差程度 |
|----------|---------|:---:|
| DAG 有向无环图，跨路线汇合 (§2.2, §2.4) | 3 条完全独立的线性路径，无交叉 | **显著偏差** |
| 4-5 次有意义的用户选择 (§2.3) | 1 次真实选择 + 4 次无后果的流程性选项 | **显著偏差** |
| 汇合节点叙事兼容多条入边 (§7.2) | 无真正的多入边节点，约束未实际验证 | **无机会验证** |
| 选项导向不同节点 (§2.4, §2.5 公式) | 12/13 节点所有选项导向单一节点 | **显著偏差** |
| 固定 3 结局收敛 (§2.2) | 达成 | ✅ |
| 节点 ≤25 (§2.3) | 达成 (16) | ✅ |
| 路线差异化 (§7.1) | 达成 (三条不同价值观) | ✅ |
| 角色行为一致性 (§7.2, §11) | 达成 | ✅ |
| 图片 placeholder (§5) | 达成 (全部 skipped) | ✅ |
| narrative 300-600 字 (§7.2) | 达成 | ✅ |

---

## 六、当前实现效果总结

### 6.1 架构实现效果

Branch Narrative Agent 的**工程骨架完整且与 SDD 高度对齐**：四阶段流程全部实现，数据模型匹配，10 个模块文件职责清晰，CLI 集成完成，图片接口预留，fallback 机制就位，38 个测试通过。

### 6.2 产出实际效果

**是一个"三选一 + 沉浸式阅读"体验，而非 SDD 设计的"4-5 次有意义选择驱动的分支 DAG"。**

具体表现：
- 用户在开场面临 1 次有意义的二阶选择（三条路线），此后经历 4 次过程性选择，但这些选择不改变叙事路径——无论选 A 还是 B，都走到同一个下一节点
- 3 条路线之间完全独立，没有跨路线汇合——用户一旦选择路线就无法"漂移"到其他路线
- 叙事文本本身质量好（prose 流畅、角色一致、承接正片），但作为"互动分支叙事"，选择的机械后果几乎为零

### 6.3 根因

根因在 Phase 1 的 DAG 骨架生成——LLM 产出的骨架结构与 fallback 方案类似，均为 3 条独立路线、每层 3 个节点、路线内各选项收束到同一节点。`_ensure_terminal_edges()` 函数进一步强化了"同一路线 → 确定结局"的映射。Phase 4 的 G7 汇合校验仅检查 indegree≥2，无法甄别"单父节点多选项汇入"与"跨父节点汇合"的本质差异。

### 6.4 是否达标

对照 SDD 的 5 项核心规格：
- ✅ 收敛架构 (3 结局, ≤25 节点, 4-5 层)
- ❌ DAG 跨路线汇合
- ✅ 数据结构 (Node/Choice/Ending)
- ❌ 4-5 次有意义选择
- ✅ 角色一致性 + 叙事质量

**3/5 核心规格达成，2/5 未达成。DAG 汇合与选择分叉是 SDD 的核心设计意图（§2.1 "不用树，用 DAG"，§2.4 示意图明确展示跨路线汇合），这两项的偏离导致产出本质上不是 SDD 设计的"分支 DAG"体验。**
