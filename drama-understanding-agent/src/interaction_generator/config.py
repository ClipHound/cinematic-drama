from __future__ import annotations

SCHEMA_VERSION = "1.0"
MANIFEST_VERSION = "1.0.0"
SIGNAL_SOURCE = "offline_video_understanding"
MIN_CONFIDENCE = 0.65
MIN_GAP_MS = 6000
DEFAULT_WINDOW_MS = 9000

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

HIGHLIGHT_TO_COMPONENT = {
    "success": "celebrate_confetti",
    "anger": "anger_release",
    "sad": "tear_resonance",
    "funny": "laugh_burst",
    "face_slap": "shatter_strike",
    "sweet": "sugar_storm",
    "rescue": "guardian_shield",
    "conflict": "team_cheer",
    "reversal": "prediction_card",
    "reveal": "prediction_card",
    "suspense": "clue_judge_card",
    "cliffhanger": "episode_end_prediction",
    "pressure": "emotion_buffer",
}

HIGHLIGHT_TO_EMOTION = {
    "success": "happy",
    "anger": "angry",
    "sad": "sad",
    "funny": "funny",
    "face_slap": "satisfying",
    "sweet": "sweet",
    "rescue": "guard",
    "conflict": "support",
    "reversal": "curious",
    "reveal": "curious",
    "suspense": "insight",
    "cliffhanger": "cliffhanger",
    "pressure": "buffer",
}

SCORE_TYPE_BY_COMPONENT = {
    "shatter_strike": "resonance",
    "anger_release": "resonance",
    "celebrate_confetti": "resonance",
    "laugh_burst": "resonance",
    "sugar_storm": "resonance",
    "tear_resonance": "resonance",
    "guardian_shield": "guard",
    "team_cheer": "guard",
    "prediction_card": "insight",
    "clue_judge_card": "insight",
    "episode_end_prediction": "insight",
    "emotion_buffer": "resonance",
}

KEYWORDS = {
    "sweet": ("表白", "拥抱", "甜蜜", "亲吻", "牵手", "心动", "暧昧"),
    "sad": ("哭", "离别", "牺牲", "泪", "悲", "委屈", "死亡", "去世"),
    "funny": ("尴尬", "搞笑", "荒唐", "滑稽", "反差", "吐槽"),
    "anger": ("羞辱", "欺负", "欺压", "强抢", "放肆", "嚣张", "怒", "侮辱"),
    "face_slap": ("反击", "打脸", "击倒", "秒杀", "惩罚", "活该", "碾压", "复仇"),
    "rescue": ("保护", "救", "护住", "挡", "守护"),
    "success": ("胜利", "成功", "达成", "赢", "获胜"),
    "suspense": ("线索", "伏笔", "秘密", "身份", "神秘", "真相", "悬念"),
    "pressure": ("压抑", "焦虑", "忧虑", "绝望", "高压", "凝重"),
}
