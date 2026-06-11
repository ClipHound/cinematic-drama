from __future__ import annotations


COMPONENT_LIBRARY = """
## 互动组件选择规范

### 选择原则
1. 先判断场景叙事功能：情绪宣泄、立场表达、认知参与、氛围渲染。
2. 再判断观众此刻的心理动作，不要只看角色情绪。
3. 必须检查组件硬排除规则。
4. candidate_interactions.emotion_type 只是参考，不是组件映射表。

### 组件定义

#### shatter_strike 碎屏暴击
语义: 积累的不满在此刻彻底释放，心理动作="终于解气了"。
适用: 反派被打脸、主角反击成功、证据扭转局面。
排除: 仍在积累愤怒时用 anger_release；爽感伴随悲剧时不用；喜剧为主时不用。
正例: 被诬陷多集后当众翻盘。反例: 反派刚开始嚣张。

#### anger_release 生气宣泄
语义: 观众感到义愤，心理动作="气死了/太过分了"。
适用: 被欺压、不公、施暴者嚣张、道义不对称对抗。
排除: 悲伤强于愤怒时用 tear_resonance；愤怒已释放时用 shatter_strike。
正例: 蛮夷当众羞辱、反派欺压弱小。反例: 反派已被击败。

#### sugar_storm 撒糖风暴
语义: 甜蜜升温，心理动作="嗑到了/好甜"。
适用: 暧昧对视、肢体接触、表白。
排除: 单恋未明、甜蜜只是阴谋包装。

#### team_cheer 站队助威
语义: 道义对等双方对抗，观众表达价值观偏好，心理动作="我站这边"。
适用: 两种合理价值观对抗、两个有魅力角色对决。
硬排除: 好人对坏人、施暴者对受害者、外敌入侵、民族冲突、只有一方主动施压时。
判断: 如果真心观众不会选择"反面"那方，就不能用 team_cheer。
正例: 主战派 vs 主和派。反例: 侵略者 vs 被侵略百姓。

#### guardian_shield 守护加持
语义: 角色弱势或危险，观众想保护，心理动作="撑住/别伤害他"。
适用: 受伤、被围困、逆风。
排除: 角色准备反击时用 shatter_strike；守护对象是反派时不用；愤怒强于担忧时用 anger_release。

#### prediction_card 剧情预测
语义: 悬念升起，观众猜后续，心理动作="接下来会怎样"。
适用: 反转前夕、角色面临选择、答案未揭晓。
排除: 答案显而易见、无法后续验证、判断已有线索时用 clue_judge_card。

#### clue_judge_card 线索判断
语义: 关键证据出现，观众判断意义，心理动作="这是什么意思/真假"。
适用: 关键物品、证据、推理节点。
排除: 线索意义一目了然；预测未来走向时用 prediction_card。

#### celebrate_confetti 庆祝礼炮
语义: 目标达成庆祝，心理动作="太好了/赢了"。
适用: 胜利、达成、反转成功后的庆祝瞬间。
排除: 胜利有代价或伴随牺牲；击败对手的解气应使用 shatter_strike。

#### tear_resonance 泪点共鸣
语义: 情感触动，观众心疼或感动。
适用: 离别、牺牲、委屈、压抑情绪释放。
排除: 悲伤对象是遭报应反派；愤怒明显强于悲伤时用 anger_release。

#### laugh_burst 大笑互动
语义: 明确喜剧意图，观众会出声笑，心理动作="哈哈哈"。
适用: 幽默台词、滑稽行为、喜剧反差。
硬排除: 只有荒诞/离谱/尴尬但无喜剧意图；角色在笑但观众不觉得好笑；幽默只是包装信息点。
判断: 普通观众不了解上下文也能识别这是笑点，才可使用。
正例: 一本正经做出完全错误推理。反例: 纨绔撒钱引发哄抢。

#### emotion_buffer 情绪缓冲
语义: 高压后的间隙，或无法精确匹配其他组件时兜底。
适用: 高压后需要呼吸、场景有互动价值但无明确类型。
排除: 有明确强情绪组件可用时。

#### episode_end_prediction 剧尾预测
语义: 集尾悬念，引导追看下一集。
适用: 固定放在集尾前 5-12 秒。
排除: 本集没有明确悬念，或距离集尾超过 15 秒。

### 易混淆决策
- "对峙"不一定是 team_cheer；先判断道义是否对等，不对等用 anger_release 或 guardian_shield。
- "反差"不一定是 laugh_burst；先判断是否有喜剧意图。
- "愤怒"积累中用 anger_release，已释放/打脸用 shatter_strike。
- "好笑"要问观众真的会笑，还是只觉得离谱/荒诞。

### config 必填字段
- prediction_card: config.options = [{text, is_correct}]，至少 2 个选项。
- clue_judge_card: config.clue_text = "线索描述"。
- team_cheer: config.sides = [{label, character}]，至少 2 个阵营，且双方道义必须对等。
"""


ALLOWED_COMPONENTS = {
    "celebrate_confetti",
    "anger_release",
    "tear_resonance",
    "laugh_burst",
    "shatter_strike",
    "sugar_storm",
    "guardian_shield",
    "team_cheer",
    "prediction_card",
    "clue_judge_card",
    "episode_end_prediction",
    "emotion_buffer",
}
