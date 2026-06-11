# Iteration V3: 组件选择质量改进 — 组件库升级 + 语义防护

> 基于 ANALYSIS-component-selection-errors.md, ROOT-CAUSE-IP2-IP5.md, INTERACTION-COMPONENT-GUIDE.md 的分析
> 日期: 2026-06-10
> 执行人: 代码助手

---

## 问题本质

两个典型错误暴露了系统性缺陷：

| 错误 | 表现 | VLM 是否有误 | Agent 2 推理 | 根因 |
|------|------|:---:|---|---|
| IP5: 蛮夷辱国 → team_cheer | 让观众在"示例王朝"和"蛮夷"之间站队 | ❌ VLM 正确 (tense+angry) | 看到"对峙" → 匹配 team_cheer | 组件库无排除规则 |
| IP2: 撒金撩女 → laugh_burst | 标记为"大笑"，但场景不好笑 | ⚠️ 标签粗 (用 funny 近似荒诞) | 看到"funny" → 匹配 laugh_burst | 情绪标签粒度 + 组件库无排除规则 |

**传播链路分析：**

```
IP5: 视频(正邪分明) → VLM(✅ tense+angry) → Agent2(看到"对峙"关键词) → 旧组件库("对峙"→team_cheer，无排除) → ❌错误
IP2: 视频(荒诞离谱) → VLM(⚠️ funny+shocking，无absurd标签) → Agent2(看到"funny") → 旧组件库("反差笑点"→laugh_burst，无排除) → ❌错误
```

核心问题在三个层面：
1. **组件库描述过于简陋** — 每个组件只有一行正向触发词，没有排除规则、没有正反例
2. **VLM 情绪标签粒度不足** — 9 种标签覆盖不了短剧的精细情感
3. **Agent 2 缺乏"质疑上游"能力** — 当 VLM 说 funny，Agent 2 不会追问"这真的好笑吗？"

---

## 解决方案

### 改进策略

已有 `INTERACTION-COMPONENT-GUIDE.md` 提供了完整的 12 组件规范（含 P1-P5 五层定义），这是正确的标准。**问题不是标准不存在，而是当前代码中的组件库描述没有使用这个标准。**

改进路径：
1. 将 `INTERACTION-COMPONENT-GUIDE.md` 的核心信息注入 Agent 2 的 Prompt（组件库升级）
2. 在 safety_rules.py 中新增硬排除校验（代码防护层）
3. 扩展 VLM 情绪标签体系（上游信号改善）

---

## 改进 A: 组件库 Prompt 升级 (P0 — 核心改动)

**当前状态**: `component_library.py` 中的 `COMPONENT_LIBRARY` 是 28 行简陋文本，每个组件只有"一句话定义 + 适合什么 + emotion="。

**目标**: 替换为结构化的组件规范，包含：
- P1: 核心语义（什么心理动作）
- P3: 硬排除规则（什么时候绝对不能用）
- P5: 正例 + 反例

**不需要全量注入**（那会让 Prompt 太长）。提取每个组件的关键判断信息，压缩到合理长度。

**改动文件**: `src/interaction_designer/component_library.py`

将 `COMPONENT_LIBRARY` 替换为以下内容：

```python
COMPONENT_LIBRARY = """
## 互动组件选择规范

### 选择原则（按顺序判断）
1. 先判断场景的叙事功能（情绪宣泄/立场表达/认知参与/氛围渲染）
2. 再判断观众此刻最主要的心理动作（不是角色的情绪，是观众的反应）
3. 检查该组件的硬排除规则
4. 情绪标签（emotion_type）只是参考信号，不是选择依据

### 组件定义

#### shatter_strike 碎屏暴击
语义: 观众积累的不满在此刻获得彻底释放。心理动作="终于解气了"
适用: 反派被打脸、主角反击成功、关键证据扭转局面
排除: ❌仍在积累愤怒时(用anger_release) ❌爽感伴随悲剧时 ❌喜剧为主时
正例: 被诬陷多集后当众翻盘
反例: 反派刚开始嚣张（仍在积累，用anger_release）

#### anger_release 生气宣泄
语义: 观众在当前场景感到义愤。心理动作="气死了/太过分了"
适用: 被欺压、不公、施暴者嚣张、道义不对称的对抗
排除: ❌悲伤强于愤怒时(用tear_resonance) ❌愤怒已经释放/已打脸时(用shatter_strike)
正例: 蛮夷当众羞辱、反派欺压弱小
反例: 反派已被击败后

#### sugar_storm 撒糖风暴
语义: 甜蜜升温。心理动作="嗑到了/好甜"
适用: 暧昧对视、肢体接触、表白
排除: ❌单恋/暗恋未明时 ❌甜蜜场景主要用于推动阴谋
正例: 双向暧昧的眼神交汇
反例: 男主对不知情的女主温柔只为套取情报

#### team_cheer 站队助威
语义: 道义对等的双方对抗，观众表达价值观偏好。心理动作="我站这边"
适用: 两种合理价值观对抗、两个有魅力的角色对决
排除: ❌❌❌ 好人对坏人/施暴者对受害者（道义不对等）→ 改用anger_release
       ❌❌❌ 外敌入侵/民族冲突等立场天然确定的场景 → 改用anger_release或guardian_shield
       ❌ 只有一方主动行动另一方被动承受时
判断: 如果把两方选项摆出来，是否真有观众会真心选择"反面"那方？如果不会，就不能用team_cheer
正例: 主战派vs主和派辩论（两种合理立场）
反例: 侵略者vs被侵略百姓（不能让观众"选择支持侵略"）

#### guardian_shield 守护加持
语义: 角色处于危险/弱势，观众产生保护欲。心理动作="撑住/别伤害他"
适用: 受伤、被围困、逆风
排除: ❌角色准备反击时(用shatter_strike) ❌守护对象是反派时 ❌愤怒强于担忧时(用anger_release)
正例: 角色孤身面对数量悬殊的敌人
反例: 角色已经掌控局面

#### prediction_card 剧情预测
语义: 悬念升起，观众猜测后续走向。心理动作="接下来会怎样"
适用: 反转前夕、角色面临选择、答案未揭晓
排除: ❌答案显而易见时 ❌无法在后续验证时 ❌判断已有线索时(用clue_judge_card)
正例: 角色收到两封密信必须选择其一
反例: 主角明显会获胜的战斗

#### clue_judge_card 线索判断
语义: 关键证据出现，观众判断其意义。心理动作="这是什么意思/真假"
适用: 关键物品、证据、推理节点
排除: ❌线索意义一目了然时 ❌问题是预测未来走向时(用prediction_card)
正例: 出现一封字迹可疑的信件
反例: 已经有旁白解释了线索含义

#### celebrate_confetti 庆祝礼炮
语义: 目标达成的庆祝。心理动作="太好了/赢了"
适用: 胜利、达成、反转成功后的庆祝瞬间
排除: ❌胜利有代价/伴随牺牲时 ❌是击败对手的解气(用shatter_strike)
正例: 主角通过考验获得认可
反例: 打败反派的快感（是shatter_strike）

#### tear_resonance 泪点共鸣
语义: 情感触动，观众会湿眼眶。心理动作="好感动/心疼"
适用: 离别、牺牲、委屈、压抑情绪的释放
排除: ❌悲伤对象是遭报应的反派时 ❌愤怒明显强于悲伤时(用anger_release)
正例: 坚强角色终于在信任的人面前哭了
反例: 反派的悲惨过去（观众以厌恶为主）

#### laugh_burst 大笑互动
语义: 明确的喜剧意图，观众会出声笑。心理动作="哈哈哈"
适用: 有意设计的幽默台词、滑稽行为、喜剧反差
排除: ❌❌❌ 只有荒诞/离谱/尴尬但没有喜剧意图时 → 改用emotion_buffer或不设点
       ❌ 角色在笑但观众不会觉得好笑时
       ❌ 幽默只是包装、场景主要传递信息时
判断: 不了解上下文的普通观众能否明确识别这是一个笑点？如果不确定，就不能用
正例: 角色一本正经做出完全错误的推理
反例: 纨绔撒钱引发哄抢（是建立人设的荒诞，不是喜剧笑点）

#### emotion_buffer 情绪缓冲
语义: 高压后的间隙，或不能精确匹配其他组件时的兜底
适用: 高压后需要呼吸、场景有互动价值但不属于以上任何明确类型
排除: ❌有明确的强情绪对应组件可用时
正例: 紧张对峙后镜头切到安静场景
反例: 有明确喜剧笑点（应用laugh_burst）

#### episode_end_prediction 剧尾预测
语义: 集尾悬念，引导追看下一集
适用: 固定放在集尾前5-12秒
排除: ❌本集没有明确悬念时 ❌距离集尾超过15秒时

### 易混淆决策
- "对峙"不一定是team_cheer——先判断道义是否对等。不对等→anger_release或guardian_shield
- "反差"不一定是laugh_burst——先判断是否有喜剧意图。无意图→emotion_buffer或不设点
- "愤怒"区分阶段：积累中→anger_release，已释放/打脸→shatter_strike
- "好笑"先问：观众真的会笑吗？还是只是觉得离谱/荒诞？

### config 必填字段
- prediction_card: config.options = [{text, is_correct}]，至少2选项
- clue_judge_card: config.clue_text = "线索描述"
- team_cheer: config.sides = [{label, character}]，至少2阵营，且双方道义必须对等
"""
```

**Token 估算**: 新组件库约 1800 字 ≈ 900 tokens（原来约 400 tokens）。增加 500 tokens 是可接受的代价——换取的是组件选择正确率的质变。

---

## 改进 B: Safety Rules 新增硬排除校验 (P0)

即使 Prompt 升级后 LLM 仍有概率犯错，需要代码层面的最后防线。

**改动文件**: `src/interaction_designer/safety_rules.py`

新增函数 `_check_exclusion_rules()`，在 `_normalize_point()` 中调用：

```python
# === 组件硬排除规则 ===

# 负面情绪关键词（标示场景道义不对等 / 非喜剧）
_NEGATIVE_MORAL_KEYWORDS = {
    "欺压", "强抢", "羞辱", "侮辱", "霸凌", "施暴", "嚣张", "猖狂",
    "蛮夷", "入侵", "侵略", "敌军", "杀害", "迫害", "虐待",
}
_ABSURD_NOT_FUNNY_KEYWORDS = {
    "荒诞", "离谱", "荒唐", "挥霍", "败家", "纨绔", "人设",
}


def _check_exclusion_rules(
    point: dict[str, Any],
    episode_context: dict[str, Any],
    repairs: list[str],
) -> dict[str, Any]:
    """
    基于硬排除规则检查组件选择。如果违反，自动替换为更合适的组件。
    """
    component = point.get("component", "")
    # 从多个字段中提取场景语义信号
    signals = " ".join([
        str(point.get("key_line", "")),
        str(point.get("highlight_reason", "")),
        str(point.get("key_visual", "")),
        str(point.get("title", "")),
    ]).lower()
    emotion = str(point.get("emotion", ""))

    # --- team_cheer 排除: 道义不对称场景 ---
    if component == "team_cheer":
        has_negative_moral = any(kw in signals for kw in _NEGATIVE_MORAL_KEYWORDS)
        has_anger_emotion = emotion in ("angry", "tense", "anger")
        
        if has_negative_moral or has_anger_emotion:
            # 道义不对称 → 降级为 anger_release
            old_component = component
            point["component"] = "anger_release"
            point["emotion"] = "angry"
            point["score_type"] = "resonance"
            # 清除不适用的 config.sides
            point["config"] = {}
            repairs.append(
                f"G16: {old_component} → anger_release "
                f"(道义不对称场景不适合站队: '{signals[:40]}...')"
            )

    # --- laugh_burst 排除: 非喜剧荒诞场景 ---
    elif component == "laugh_burst":
        has_absurd_signal = any(kw in signals for kw in _ABSURD_NOT_FUNNY_KEYWORDS)
        # 如果上游情绪不是纯 funny（含 shocking/tense 等复合情绪）
        emotion_ambiguous = "shocking" in emotion or "tense" in emotion
        
        if has_absurd_signal and not _has_clear_comedy_signal(signals):
            old_component = component
            point["component"] = "emotion_buffer"
            point["emotion"] = "buffer"
            point["score_type"] = "resonance"
            repairs.append(
                f"G17: {old_component} → emotion_buffer "
                f"(荒诞/离谱场景无明确喜剧意图: '{signals[:40]}...')"
            )

    return point


def _has_clear_comedy_signal(signals: str) -> bool:
    """检查是否有明确的喜剧信号"""
    comedy_keywords = {"笑", "搞笑", "滑稽", "幽默", "笨拙", "尴尬", "反应迟钝", "误会"}
    return any(kw in signals for kw in comedy_keywords)
```

**集成点** — 在现有 `normalize_design_output()` 中，对每个 point 调用：

```python
# 在 _normalize_point 中，component 白名单检查之后追加:
point = _check_exclusion_rules(point, episode_context, repairs)
```

---

## 改进 C: VLM 情绪标签体系扩展 (P1)

**当前状态**: VLM 的 `emotion_type` 只有 9 种：
```
anger | sweet | funny | sad | shocking | satisfying | tense | curious | guard
```

**问题**: "荒诞" 只能用 `funny+shocking` 近似表达，导致 Agent 2 误读为"好笑"。

**方案**: 扩展为 13 种（新增 4 种高频短剧情感）：

```
anger | sweet | funny | sad | shocking | satisfying | tense | curious | guard
+ absurd | indignant | bittersweet | anticipation
```

| 新增标签 | 语义 | 替代了什么 |
|---------|------|-----------|
| `absurd` | 荒诞/离谱/荒唐 (不是好笑) | 之前被标为 funny+shocking |
| `indignant` | 义愤/愤懑 (比 anger 更聚焦于道德感) | 之前被标为 tense+anger |
| `bittersweet` | 又甜又虐/苦涩感动 | 之前被标为 sad+sweet |
| `anticipation` | 期待/跃跃欲试 (不是好奇) | 之前被标为 curious |

**改动文件**: `src/drama_agent/model/prompts.py`

```python
# 修改 emotion_type 枚举行:
"emotion_type": "anger|sweet|funny|sad|shocking|satisfying|tense|curious|guard|absurd|indignant|bittersweet|anticipation",
```

并在 prompt 说明中追加一行引导：
```python
# 在 candidate_interactions 要求后追加:
"""
emotion_type 选择指引:
- funny: 观众会出声笑的喜剧场景。如果只是离谱/荒诞但不好笑，用 absurd。
- anger: 一般性愤怒。如果是道义感强烈的愤怒（不公、施暴），用 indignant。
- sad + sweet 并存时: 用 bittersweet。
- curious 但侧重"等不及想看结果"时: 用 anticipation。
"""
```

**向下兼容**: Agent 2 (pass2_episode.py) 收到新标签后不影响组件选择——因为组件库已经明确"emotion 只是参考信号，不是选择依据"。safety_rules 中 `_check_exclusion_rules` 也已覆盖 `absurd` 场景（归入 _ABSURD_NOT_FUNNY_KEYWORDS 检测）。

---

## 改进 D: Pass 2 Prompt 新增"质疑上游"指令 (P1)

**问题**: Agent 2 对 VLM 的 emotion_type 是完全信任模式。如果 VLM 标了 funny，Agent 2 不会质疑。

**方案**: 在 Pass 2 Prompt 中追加"独立判断"指令。

**改动文件**: `src/interaction_designer/pass2_episode.py`

在 `build_episode_prompt()` 的指令列表中追加：

```python
# 在 "你必须自主判断，而不是机械映射:" 后面追加:
"""
9. 不要盲目相信 candidate_interactions 的 emotion_type。它是 VLM 对视频的初步标注，可能有偏差。
   你需要根据 reason、anchor_line、visual_cue 独立判断观众此刻的真实心理反应。
   特别注意：
   - "funny" 不一定真的好笑 → 问自己：普通观众会出声笑吗？
   - "对峙"不一定适合站队 → 问自己：双方道义是否对等？有没有明确的正邪之分？
   - "反差"不等于"喜剧反差" → 问自己：这个反差的功能是搞笑还是建立人设/制造震撼？
"""
```

---

## 执行顺序

```
改进 A (组件库 Prompt 升级)      ← 最高优先级，直接决定 LLM 选择质量
    ↓
改进 D (Pass 2 "质疑上游"指令)   ← 与 A 一起改 pass2_episode.py
    ↓
改进 B (Safety Rules 硬排除)     ← 代码防线，兜底
    ↓
改进 C (VLM 情绪标签扩展)        ← 改上游，需要重新跑理解流程才能生效
```

---

## 验证方案

### 验证 1: 单元测试新增

**新建**: `tests/test_exclusion_rules.py`

```python
"""测试组件硬排除规则"""
import pytest
from interaction_designer.safety_rules import _check_exclusion_rules


class TestTeamCheerExclusion:
    """team_cheer 道义不对称排除"""

    def test_team_cheer_with_violence_keyword(self):
        point = {
            "component": "team_cheer",
            "emotion": "support",
            "key_line": "蛮夷当众强抢民女",
            "highlight_reason": "对峙场景",
            "key_visual": "",
            "title": "",
            "config": {"sides": [{"label": "示例王朝"}, {"label": "蛮夷"}]},
            "score_type": "cocreate",
        }
        repairs = []
        result = _check_exclusion_rules(point, {}, repairs)
        assert result["component"] == "anger_release"
        assert result["emotion"] == "angry"
        assert result["config"] == {}
        assert any("G16" in r for r in repairs)

    def test_team_cheer_with_angry_emotion(self):
        point = {
            "component": "team_cheer",
            "emotion": "angry",
            "key_line": "就连你们的皇帝来了都得卑躬屈膝",
            "highlight_reason": "嚣张蛮夷挑衅",
            "key_visual": "", "title": "",
            "config": {"sides": []},
            "score_type": "cocreate",
        }
        repairs = []
        result = _check_exclusion_rules(point, {}, repairs)
        assert result["component"] == "anger_release"

    def test_team_cheer_valid_scenario(self):
        """道义对等的场景不应被排除"""
        point = {
            "component": "team_cheer",
            "emotion": "support",
            "key_line": "主战派认为应该迎击，主和派认为应该议和",
            "highlight_reason": "两种合理立场的对抗",
            "key_visual": "", "title": "",
            "config": {"sides": [{"label": "主战"}, {"label": "主和"}]},
            "score_type": "cocreate",
        }
        repairs = []
        result = _check_exclusion_rules(point, {}, repairs)
        assert result["component"] == "team_cheer"  # 不应被替换
        assert len(repairs) == 0


class TestLaughBurstExclusion:
    """laugh_burst 非喜剧荒诞排除"""

    def test_laugh_burst_absurd_but_not_funny(self):
        point = {
            "component": "laugh_burst",
            "emotion": "funny",
            "key_line": "今天全场消费都由本公子买单",
            "highlight_reason": "纨绔人设建立，荒诞挥霍",
            "key_visual": "银票满地，女子哄抢",
            "title": "撒金",
            "config": {},
            "score_type": "resonance",
        }
        repairs = []
        result = _check_exclusion_rules(point, {}, repairs)
        assert result["component"] == "emotion_buffer"
        assert any("G17" in r for r in repairs)

    def test_laugh_burst_genuine_comedy(self):
        """有明确喜剧信号时不应被排除"""
        point = {
            "component": "laugh_burst",
            "emotion": "funny",
            "key_line": "他一本正经说了句完全搞笑的推理",
            "highlight_reason": "滑稽的推理让人笑喷",
            "key_visual": "", "title": "",
            "config": {},
            "score_type": "resonance",
        }
        repairs = []
        result = _check_exclusion_rules(point, {}, repairs)
        assert result["component"] == "laugh_burst"  # 不应被替换
        assert len(repairs) == 0
```

### 验证 2: 端到端回归

```bash
# 清理旧输出
rm -rf outputs/example-drama-a-v3

# 重新跑互动设计（使用已有 test-5eps-v2 的理解结果）
drama-agent design-interactions \
  --project projects/test-5eps-v2 \
  --output-dir outputs/example-drama-a-v3 \
  --drama-id example-drama-a

# 检查是否有 G16/G17 修复触发
python -c "
import json
from pathlib import Path
for f in sorted(Path('outputs/example-drama-a-v3/example-drama-a').glob('*.json')):
    data = json.loads(f.read_text(encoding='utf-8'))
    repairs = data.get('design_repairs', [])
    if any('G16' in r or 'G17' in r for r in repairs):
        print(f'{f.name}: exclusion rules triggered')
        for r in repairs:
            if 'G16' in r or 'G17' in r:
                print(f'  {r}')
    # 检查是否还有 team_cheer + 道义不对称的情况残留
    for p in data.get('interaction_points', []):
        if p['component'] == 'team_cheer':
            line = p.get('key_line', '')
            reason = p.get('highlight_reason', '')
            print(f'{f.name}/{p[\"id\"]}: team_cheer, line={line[:30]}, reason={reason[:30]}')
        if p['component'] == 'laugh_burst':
            reason = p.get('highlight_reason', '')
            print(f'{f.name}/{p[\"id\"]}: laugh_burst, reason={reason[:30]}')
"
```

### 验证 3: 改进 C 验证（需要重新跑理解）

```bash
# 改进 C 修改了 VLM prompt，需要重新跑理解才能看到效果
# 只跑第 1 集验证新情绪标签是否出现
rm -rf projects/test-ep1-v3

drama-agent run \
  --title "示例剧A" \
  --video-dir "<project-root>/样例剧(测试使用)" \
  --pattern "第{num}集.mp4" \
  --episodes 1 \
  --project-id test-ep1-v3

# 检查新标签是否被使用
python -c "
import json
data = json.loads(open('projects/test-ep1-v3/action_plans/ep01.json', encoding='utf-8').read())
for ci in data.get('candidate_interactions', []):
    print(f'[{ci[\"start_ms\"]}-{ci[\"end_ms\"]}] emotion={ci[\"emotion_type\"]} | {ci.get(\"anchor_line\",\"\")[:30]}')
"
# 期望: 撒金场景标为 absurd 或 absurd+shocking
# 期望: 蛮夷场景标为 indignant 或 anger
```

---

## 改动文件汇总

| 文件 | 动作 | 对应改进 |
|------|------|---------|
| `src/interaction_designer/component_library.py` | **重写** COMPONENT_LIBRARY | A |
| `src/interaction_designer/pass2_episode.py` | 修改 (追加指令 9) | D |
| `src/interaction_designer/safety_rules.py` | 修改 (新增 _check_exclusion_rules + G16/G17) | B |
| `src/drama_agent/model/prompts.py` | 修改 (扩展 emotion_type + 选择指引) | C |
| `tests/test_exclusion_rules.py` | **新建** | B 验证 |

---

## 注意事项

1. **改进 A 的组件库长度控制**: 新的 COMPONENT_LIBRARY 约 1800 字。加上 episode_context（候选点+ASR+plot_events+密度约束），总 Prompt 不应超过 8000 tokens。如果超过，优先压缩 episode_context 中的 ASR 部分（已经是句级了）。

2. **改进 B 的关键词表是有限集**: `_NEGATIVE_MORAL_KEYWORDS` 和 `_ABSURD_NOT_FUNNY_KEYWORDS` 是初始集，会有遗漏。但这是兜底层——第一道防线是 Prompt（改进 A+D），关键词检测是最后防线。后续可以持续补充。

3. **改进 C 需要谨慎**: 扩展 VLM 情绪标签意味着旧的 action_plan 和新的不兼容。只对新跑的项目生效。已有的 test-5eps-v2 不会自动受益，除非重跑理解阶段。

4. **改进 A 和 D 改完后可以直接用已有数据验证**: 不需要重跑理解阶段。只需重跑 `design-interactions` 即可看到效果（Agent 2 消费的是已有的 candidate_interactions）。

5. **不要删除旧的 ALLOWED_COMPONENTS 集合**: 它仍然用于白名单校验。组件库内容升级不影响允许列表。

---

> 改进 A+D 改完后立即重跑互动设计验证效果；改进 B 补充代码防线；改进 C 最后做（影响面最大，需要重跑理解）。
