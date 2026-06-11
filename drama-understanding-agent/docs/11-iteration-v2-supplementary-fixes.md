# Iteration V2 补充修复: 审核报告发现项

> 基于 REVIEW-multi-agent-and-interaction-design.md 的审核反馈
> 日期: 2026-06-10
> 前置依赖: 先完成 `docs/10-iteration-v2-improvements.md` 中的改进 1-6
> 执行人: 代码助手

---

## 背景

第三方审核报告在产出质量层面发现 3 个具体问题，均可在 safety_rules 和 agent 编排层修复，不涉及 Prompt 重写或架构变更。

---

## 修复 7: score_type 白名单校验

**问题**: LLM 偶尔输出不在预定义集合中的 score_type 值（如 `"emotional"`, `"drama"` 等），前端只认 4 种。

**允许值**: `resonance | guard | insight | cocreate`

**改动文件**: `src/interaction_designer/safety_rules.py`

**方案**:

```python
ALLOWED_SCORE_TYPES = {"resonance", "guard", "insight", "cocreate"}

# 在 _normalize_point() 中追加:
score_type = point.get("score_type", "")
if score_type not in ALLOWED_SCORE_TYPES:
    # 根据组件语义推断合理的 fallback
    score_type = _infer_score_type(component)
    repairs.append(f"G14: score_type '{point.get('score_type')}' invalid, inferred as '{score_type}'")
point["score_type"] = score_type
```

**推断规则** (新增 helper):

```python
def _infer_score_type(component: str) -> str:
    """根据组件语义推断 score_type"""
    mapping = {
        "guardian_shield": "guard",
        "prediction_card": "insight",
        "clue_judge_card": "insight",
        "episode_end_prediction": "insight",
        "team_cheer": "cocreate",
    }
    return mapping.get(component, "resonance")
```

**验证**:

```bash
python -c "
import json
from pathlib import Path
for f in sorted(Path('outputs/example-drama-a').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    for p in data.get('interaction_points', []):
        st = p.get('score_type', '')
        assert st in {'resonance','guard','insight','cocreate'}, f'{p[\"id\"]}: invalid score_type={st}'
    print(f'{f.name}: all score_types valid')
"
```

---

## 修复 8: G9 集间主题去重

**问题**: SDD 第 4.6 节 G9 规则要求"连续 3 集不能使用完全相同的互动主题组合"，当前未实现。实测 Ep1 和 Ep5 都以 `anger_release` 开头 + `shatter_strike` 或 `prediction_card` 结尾，虽然不严重但随着集数增加可能单调。

**定义**: "互动主题" = 该集使用的 component 集合（忽略顺序）。连续 3 集不能有完全相同的 component 集合。

**方案**: 在 `agent.py` 的逐集循环中追加集间状态检查

**改动文件**: `src/interaction_designer/agent.py`

```python
class InteractionDesignAgent:
    def run(self, ...) -> list[DesignResult]:
        ...
        recent_component_sets: list[set[str]] = []  # 滑动窗口，保存最近 2 集的组件集合
        
        for episode_num in episode_numbers(ctx):
            episode_context = build_episode_context(ctx, episode_num, blueprint)
            
            # 注入集间去重提示
            episode_context["recent_themes"] = [
                sorted(s) for s in recent_component_sets[-2:]
            ]
            
            design = run_episode_pass(self.llm, episode_context)
            ...
            # normalize 后记录本集组件集合
            components_used = {p["component"] for p in design.get("interaction_points", [])}
            
            # G9 检查: 如果连续 3 集完全相同，追加 warning
            if len(recent_component_sets) >= 2 and components_used == recent_component_sets[-1] == recent_component_sets[-2]:
                design.setdefault("warnings", []).append(
                    f"G9: 连续3集使用相同组件集合 {sorted(components_used)}"
                )
            
            recent_component_sets.append(components_used)
            ...
```

**Pass 2 Prompt 补充** (在 `pass2_episode.py` 的 `build_episode_prompt` 中):

```python
# 如果有 recent_themes，注入提示
recent = episode_context.get("recent_themes", [])
if recent:
    recent_hint = f"""
前两集已使用的组件: {recent}
请尽量避免与前两集完全相同的组件组合，保持互动体验的新鲜感。
"""
else:
    recent_hint = ""
```

**验证**:

```bash
python -c "
import json
from pathlib import Path
sets = []
for i in range(1, 6):
    f = Path(f'outputs/example-drama-a/ep_{i:03d}.interactions.json')
    data = json.loads(f.read_text(encoding='utf-8'))
    components = frozenset(p['component'] for p in data.get('interaction_points', []))
    sets.append(components)
    print(f'Ep{i}: {sorted(components)}')

# Check G9
for i in range(2, len(sets)):
    if sets[i] == sets[i-1] == sets[i-2]:
        print(f'⚠ G9 violation: Ep{i-1}-Ep{i}-Ep{i+1} all identical')
    else:
        print(f'✓ G9 ok at Ep{i+1}')
"
```

---

## 修复 9: config 字段非空校验 (组件特定)

**问题**: 某些组件需要 config 中有特定字段才能被前端正确渲染，但 LLM 经常输出空的 `config: {}`。

**组件 config 需求表**:

| 组件 | config 必需字段 | 说明 |
|------|----------------|------|
| prediction_card | `options: [{text, is_correct}]` | 至少 2 个选项 |
| episode_end_prediction | `options: [{text, reveal_episode_id}]` | 至少 2 个选项 |
| clue_judge_card | `clue_text: str` | 线索描述文本 |
| team_cheer | `sides: [{label, character}]` | 至少 2 个阵营 |

其余组件（shatter_strike, anger_release, sugar_storm, celebrate_confetti, tear_resonance, laugh_burst, emotion_buffer, guardian_shield）允许空 config。

**方案**: 在 safety_rules.py 中追加 config 校验和自动填充

**改动文件**: `src/interaction_designer/safety_rules.py`

```python
REQUIRED_CONFIG: dict[str, list[str]] = {
    "prediction_card": ["options"],
    "episode_end_prediction": ["options"],
    "clue_judge_card": ["clue_text"],
    "team_cheer": ["sides"],
}

def _validate_config(point: dict, repairs: list[str]) -> dict:
    """校验并修复组件特定 config 字段"""
    component = point.get("component", "")
    config = point.get("config") or {}
    required = REQUIRED_CONFIG.get(component, [])
    
    for field in required:
        if field not in config or not config[field]:
            # 尝试从 point 其他字段推断
            if field == "options" and component == "prediction_card":
                config["options"] = _infer_prediction_options(point)
                repairs.append(f"G15: auto-filled config.options for {point.get('id')}")
            elif field == "clue_text" and component == "clue_judge_card":
                config["clue_text"] = point.get("key_line") or point.get("highlight_reason") or "关键线索"
                repairs.append(f"G15: auto-filled config.clue_text for {point.get('id')}")
            elif field == "sides" and component == "team_cheer":
                config["sides"] = _infer_team_sides(point)
                repairs.append(f"G15: auto-filled config.sides for {point.get('id')}")
            elif field == "options" and component == "episode_end_prediction":
                # episode_end_prediction 的 options 通常在 episode_end_interaction 中
                # 如果 config 为空，留空不填（episode_end 有独立字段）
                pass
    
    point["config"] = config
    return point


def _infer_prediction_options(point: dict) -> list[dict]:
    """从 highlight_reason 推断预测选项"""
    return [
        {"text": "会发生", "is_correct": True},
        {"text": "不会发生", "is_correct": False},
    ]


def _infer_team_sides(point: dict) -> list[dict]:
    """从 key_line 推断站队阵营"""
    return [
        {"label": "支持", "character": "主角"},
        {"label": "反对", "character": "对手"},
    ]
```

**注意**: 自动推断的 options/sides 是兜底行为，质量不高。更好的方案是在 Pass 2 Prompt 中明确要求 LLM 对这些组件输出 config。所以同步修改 Prompt:

**改动文件**: `src/interaction_designer/pass2_episode.py`

在 Prompt 的组件说明区域追加:

```
注意: 以下组件必须在 config 中提供特定字段:
- prediction_card: config.options = [{text: "选项文本", is_correct: true/false}] (至少2个选项)
- clue_judge_card: config.clue_text = "需要判断的线索描述"
- team_cheer: config.sides = [{label: "阵营名", character: "代表角色"}] (至少2个阵营)
```

**验证**:

```bash
python -c "
import json
from pathlib import Path

REQUIRED = {
    'prediction_card': ['options'],
    'clue_judge_card': ['clue_text'],
    'team_cheer': ['sides'],
}

issues = []
for f in sorted(Path('outputs/example-drama-a').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    for p in data.get('interaction_points', []):
        comp = p.get('component', '')
        config = p.get('config', {})
        for field in REQUIRED.get(comp, []):
            if field not in config or not config[field]:
                issues.append(f'{f.name}/{p[\"id\"]}: {comp} missing config.{field}')

if issues:
    print(f'⚠ {len(issues)} config issues:')
    for i in issues:
        print(f'  {i}')
else:
    print('✓ All component configs valid')
"
```

---

## 改动文件汇总

| 文件 | 动作 | 对应修复 |
|------|------|---------|
| `src/interaction_designer/safety_rules.py` | 修改 | #7 score_type 白名单, #9 config 校验 |
| `src/interaction_designer/agent.py` | 修改 | #8 集间主题去重状态传递 |
| `src/interaction_designer/pass2_episode.py` | 修改 | #8 recent_themes 注入, #9 config 字段要求 |
| `src/interaction_designer/component_library.py` | 修改 | #9 组件 config 需求说明 (追加到 COMPONENT_LIBRARY 文本) |

---

## 执行顺序

```
修复 7 (score_type)     ← 最简单，safety_rules 加几行
    ↓
修复 9 (config 校验)    ← 同在 safety_rules + Prompt 补充
    ↓
修复 8 (G9 集间去重)    ← 改 agent.py 循环 + Prompt 补充
```

修复 7 和 9 可以一起做（都在 safety_rules.py 里），然后再做 8。

---

## 与 10-iteration-v2-improvements.md 的关系

- 先执行 `10-iteration-v2-improvements.md` 中的改进 1-6（ASR 句级合并、批量前置、蓝图持久化、密度配置、时长 fallback、时长注入 Pass 2）
- 再执行本文档的修复 7-9
- 两份文档的改动文件无冲突（本文档不改 ASR、episode_loop、output_formatter）

---

## 最终验证 (全部完成后)

```bash
# 清理旧输出
rm -rf outputs/example-drama-a-final

# 完整互动设计流程
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --output-dir outputs/example-drama-a-final \
  --drama-id example-drama-a \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4"

# 全量校验
python -c "
import json
from pathlib import Path

ALLOWED_SCORES = {'resonance','guard','insight','cocreate'}
REQUIRED_CONFIG = {
    'prediction_card': ['options'],
    'clue_judge_card': ['clue_text'],
    'team_cheer': ['sides'],
}

issues = []
component_sets = []

for f in sorted(Path('outputs/example-drama-a-final/example-drama-a').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    points = data.get('interaction_points', [])
    ep_components = set()
    
    for p in points:
        # score_type check
        if p.get('score_type') not in ALLOWED_SCORES:
            issues.append(f'{f.name}/{p[\"id\"]}: bad score_type={p.get(\"score_type\")}')
        
        # config check
        comp = p.get('component','')
        ep_components.add(comp)
        config = p.get('config', {})
        for field in REQUIRED_CONFIG.get(comp, []):
            if field not in config or not config[field]:
                issues.append(f'{f.name}/{p[\"id\"]}: {comp} missing config.{field}')
    
    component_sets.append(ep_components)

# G9 check
for i in range(2, len(component_sets)):
    if component_sets[i] == component_sets[i-1] == component_sets[i-2]:
        issues.append(f'G9: Ep{i-1}~Ep{i+1} identical component sets')

if issues:
    print(f'FAIL: {len(issues)} issues')
    for i in issues:
        print(f'  {i}')
else:
    print('PASS: score_type + config + G9 all valid')
"
```

---

> 本文档执行完毕后，系统改进全部完成。无需额外文档。
