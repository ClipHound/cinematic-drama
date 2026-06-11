from __future__ import annotations

from typing import Any

from interaction_generator.config import (
    ALLOWED_COMPONENTS,
    DEFAULT_WINDOW_MS,
    HIGHLIGHT_TO_COMPONENT,
    HIGHLIGHT_TO_EMOTION,
    SCORE_TYPE_BY_COMPONENT,
    SIGNAL_SOURCE,
)
from interaction_generator.event_to_highlight import HighlightPoint


def highlight_to_interaction_point(
    highlight: HighlightPoint,
    *,
    episode_id: str,
    index: int,
    duration_ms: int,
    key_line: str = "",
) -> dict[str, Any]:
    component = HIGHLIGHT_TO_COMPONENT.get(highlight.highlight_type, "emotion_buffer")
    if component not in ALLOWED_COMPONENTS:
        component = "emotion_buffer"
    start_ms = _bounded_start(highlight.start_ms - 500, duration_ms)
    end_ms = _bounded_end(max(highlight.end_ms, start_ms + DEFAULT_WINDOW_MS), start_ms, duration_ms)
    return {
        "id": f"ip_{episode_id}_{index:04d}",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "type": "EMOTION_INTERACTION",
        "sub_type": component,
        "component": component,
        "emotion": HIGHLIGHT_TO_EMOTION.get(highlight.highlight_type, "buffer"),
        "intensity": round(highlight.intensity, 3),
        "priority": round(highlight.priority, 3),
        "confidence": round(highlight.confidence, 3),
        "signal_source": SIGNAL_SOURCE,
        "is_verified": False,
        "title": _title_for(component),
        "highlight_reason": _reason_for(highlight),
        "key_line": key_line,
        "key_visual": highlight.key_visual,
        "score_type": SCORE_TYPE_BY_COMPONENT.get(component, "resonance"),
        "evidence": {
            "scene_start_ms": highlight.start_ms,
            "scene_end_ms": highlight.end_ms,
            "source_event_id": highlight.source_event_id,
            "reason_codes": highlight.reason_codes,
        },
        "config": _default_config(component, episode_id, index, start_ms),
    }


def _bounded_start(value: int, duration_ms: int) -> int:
    if duration_ms <= 0:
        return max(value, 0)
    return max(0, min(value, max(duration_ms - 1000, 0)))


def _bounded_end(value: int, start_ms: int, duration_ms: int) -> int:
    end_ms = max(value, start_ms + 1000)
    return min(end_ms, duration_ms) if duration_ms > 0 else end_ms


def _title_for(component: str) -> str:
    return {
        "celebrate_confetti": "庆祝礼炮",
        "anger_release": "生气宣泄",
        "tear_resonance": "泪点共鸣",
        "laugh_burst": "大笑互动",
        "shatter_strike": "碎屏暴击",
        "sugar_storm": "撒糖风暴",
        "guardian_shield": "守护加持",
        "team_cheer": "站队助威",
        "prediction_card": "剧情预测",
        "clue_judge_card": "线索判断",
        "episode_end_prediction": "剧尾预测",
        "emotion_buffer": "情绪缓冲",
    }.get(component, "互动点")


def _reason_for(highlight: HighlightPoint) -> str:
    prefix = {
        "face_slap": "反击或惩罚带来强爽点，适合触发碎屏暴击。",
        "anger": "角色遭遇羞辱或压迫，适合让观众点击宣泄。",
        "conflict": "双方关系或阵营发生对峙，适合站队助威。",
        "reveal": "关键信息揭露，适合引导观众预测后续。",
        "reversal": "剧情出现反转，适合引导观众预测真相。",
        "suspense": "场景埋下线索或悬念，适合线索判断。",
        "sweet": "亲密关系升温，适合撒糖互动。",
        "sad": "情绪压抑或委屈，适合共鸣互动。",
        "cliffhanger": "集尾悬念明确，适合预测下一集。",
    }.get(highlight.highlight_type, "剧情情绪达到阶段性峰值，适合触发互动。")
    return f"{prefix}{highlight.description}"


def _default_config(component: str, episode_id: str, index: int, start_ms: int) -> dict[str, Any]:
    if component == "shatter_strike":
        return {"particle_preset": "shatter", "haptic_type": "sharp_click"}
    if component == "anger_release":
        return {"haptic_type": "heavy_tap"}
    if component == "team_cheer":
        return {
            "timer_text": _format_timer(start_ms),
            "prompt_text": "选择阵营，为TA助威",
            "team_options": [
                {"team_key": "hero", "label": "支持主角", "color": "#ff5a66", "score": 126380},
                {"team_key": "rival", "label": "支持对方", "color": "#36c6d3", "score": 117240},
            ],
        }
    if component in {"prediction_card", "episode_end_prediction"}:
        return {
            "prediction_id": f"pred_{episode_id}_{index:03d}",
            "question": "接下来剧情会如何发展？",
            "options": [
                {"option_key": "yes", "label": "会反转"},
                {"option_key": "no", "label": "不会反转"},
            ],
        }
    if component == "clue_judge_card":
        return {
            "clue_id": f"clue_{episode_id}_{index:03d}",
            "question": "这是关键线索吗？",
            "options": [
                {"option_key": "yes", "label": "是线索"},
                {"option_key": "no", "label": "只是铺垫"},
            ],
        }
    return {}


def _format_timer(start_ms: int) -> str:
    seconds = max(start_ms // 1000, 0)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"
