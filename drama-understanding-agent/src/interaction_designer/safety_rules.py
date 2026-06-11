from __future__ import annotations

from typing import Any

from interaction_designer.component_library import ALLOWED_COMPONENTS
from interaction_designer.config import DesignConfig


ALLOWED_SCORE_TYPES = {"resonance", "guard", "insight", "cocreate"}
REQUIRED_CONFIG = {
    "prediction_card": ["options"],
    "clue_judge_card": ["clue_text"],
    "team_cheer": ["sides"],
}
_NEGATIVE_MORAL_KEYWORDS = {
    "欺压",
    "强抢",
    "羞辱",
    "侮辱",
    "霸凌",
    "施暴",
    "入侵",
    "侵略",
    "外敌",
    "杀害",
    "屠杀",
    "迫害",
    "虐待",
    "胁迫",
    "威胁",
    "掠夺",
    "凌辱",
    "受害者",
    "辱国",
    "不公",
}
_MORAL_EMOTIONS = {"angry", "anger", "indignant"}
_ABSURD_NOT_FUNNY_KEYWORDS = {
    "荒诞",
    "离谱",
    "荒唐",
    "非喜剧",
    "不是笑点",
    "人设建立",
    "信息铺垫",
    "身份伪装",
}


def normalize_design_output(
    design: dict[str, Any],
    *,
    episode_id: str,
    duration_ms: int,
    config: DesignConfig | None = None,
) -> tuple[dict[str, Any], list[str]]:
    design_config = config or DesignConfig()
    warnings: list[str] = []
    repairs: list[str] = []
    points = []
    for index, point in enumerate(design.get("interaction_points") or [], start=1):
        normalized = _normalize_point(point, episode_id, index, duration_ms, repairs, design_config)
        if normalized:
            points.append(normalized)
    points.sort(key=lambda item: item["start_ms"])
    points = _remove_overlaps(points, repairs, min_gap_ms=design_config.min_gap_ms)
    points = _limit_points(points, duration_ms, design_config, repairs)
    design["interaction_points"] = points
    warnings.extend(_validate_final(design["interaction_points"], duration_ms, design_config))
    design.setdefault("episode_end_interaction", {})
    design["repair_notes"] = repairs
    return design, warnings


def _normalize_point(
    point: dict[str, Any],
    episode_id: str,
    index: int,
    duration_ms: int,
    warnings: list[str],
    config: DesignConfig,
) -> dict[str, Any] | None:
    component = point.get("component")
    if component not in ALLOWED_COMPONENTS:
        warnings.append(f"G13: removed invalid component {component}")
        return None
    point = _check_exclusion_rules(point, {}, warnings)
    component = point.get("component")
    start = max(int(point.get("start_ms") or 0), 0)
    if duration_ms > 0:
        if duration_ms < config.min_duration_ms:
            warnings.append(f"G1: removed {point.get('id') or index}; episode shorter than minimum")
            return None
        shifted_start = min(start, duration_ms - config.min_duration_ms)
        if shifted_start != start:
            warnings.append(f"G1: shifted {point.get('id') or index} earlier near episode boundary")
        start = shifted_start
    end = int(point.get("end_ms") or start + 9000)
    if end <= start:
        end = start + 9000
    if end - start < config.min_duration_ms:
        end = start + config.min_duration_ms
    if end - start > config.max_duration_ms:
        end = start + config.max_duration_ms
        warnings.append(f"G1: clipped duration for {point.get('id') or index}")
    if duration_ms > 0 and end > duration_ms:
        end = duration_ms
        if end - start < config.min_duration_ms:
            start = max(0, end - config.min_duration_ms)
            warnings.append(f"G1: shifted {point.get('id') or index} earlier near episode boundary")
    if end - start < config.min_duration_ms:
        warnings.append(f"G1: removed {point.get('id') or index}; duration below minimum")
        return None
    if end <= start:
        return None
    point["id"] = point.get("id") or f"ip_{episode_id}_{index:04d}"
    point["start_ms"] = start
    point["end_ms"] = end
    point["type"] = point.get("type") or "EMOTION_INTERACTION"
    point["sub_type"] = point.get("sub_type") or component
    point["is_verified"] = bool(point.get("is_verified", False))
    point["signal_source"] = point.get("signal_source") or "interaction_design_agent"
    point["config"] = point.get("config") or {}
    point["score_type"] = _normalize_score_type(point, component, warnings)
    point = _validate_config(point, warnings)
    point["confidence"] = _clamp(float(point.get("confidence") or 0.75))
    point["intensity"] = _clamp(float(point.get("intensity") or 0.7))
    point["priority"] = _clamp(float(point.get("priority") or point["intensity"]))
    point.setdefault("highlight_reason", "")
    return point


def _check_exclusion_rules(
    point: dict[str, Any],
    episode_context: dict[str, Any],
    repairs: list[str],
) -> dict[str, Any]:
    component = point.get("component", "")
    signals = " ".join(
        [
            str(point.get("key_line", "")),
            str(point.get("highlight_reason", "")),
            str(point.get("key_visual", "")),
            str(point.get("title", "")),
            str(episode_context.get("summary", "")),
        ]
    ).lower()
    emotion = str(point.get("emotion", "")).lower()

    if component == "team_cheer" and _is_morally_asymmetric(signals, emotion):
        point["component"] = "anger_release"
        point["emotion"] = "angry"
        point["score_type"] = "resonance"
        point["config"] = {}
        repairs.append(f"G16: team_cheer -> anger_release (道义不对称: '{signals[:40]}...')")
    elif component == "laugh_burst" and _is_absurd_without_comedy(signals):
        point["component"] = "emotion_buffer"
        point["emotion"] = "buffer"
        point["score_type"] = "resonance"
        point["config"] = {}
        repairs.append(f"G17: laugh_burst -> emotion_buffer (非喜剧荒诞: '{signals[:40]}...')")
    return point


def _is_morally_asymmetric(signals: str, emotion: str) -> bool:
    has_moral_signal = any(keyword in signals for keyword in _NEGATIVE_MORAL_KEYWORDS)
    if has_moral_signal:
        return True
    return emotion in _MORAL_EMOTIONS and any(token in signals for token in {"对抗", "压迫", "伤害", "不公"})


def _is_absurd_without_comedy(signals: str) -> bool:
    return any(keyword in signals for keyword in _ABSURD_NOT_FUNNY_KEYWORDS) and not _has_clear_comedy_signal(signals)


def _has_clear_comedy_signal(signals: str) -> bool:
    comedy_keywords = {"笑", "搞笑", "滑稽", "幽默", "笨拙", "尴尬", "反应迟钝", "误会"}
    return any(keyword in signals for keyword in comedy_keywords)


def _normalize_score_type(point: dict[str, Any], component: str, repairs: list[str]) -> str:
    score_type = str(point.get("score_type") or "")
    if score_type in ALLOWED_SCORE_TYPES:
        return score_type
    inferred = _infer_score_type(component)
    repairs.append(f"G14: score_type '{score_type}' invalid, inferred as '{inferred}'")
    return inferred


def _infer_score_type(component: str) -> str:
    mapping = {
        "guardian_shield": "guard",
        "prediction_card": "insight",
        "clue_judge_card": "insight",
        "episode_end_prediction": "insight",
        "team_cheer": "cocreate",
    }
    return mapping.get(component, "resonance")


def _validate_config(point: dict[str, Any], repairs: list[str]) -> dict[str, Any]:
    component = point.get("component", "")
    config = point.get("config") or {}
    for field in REQUIRED_CONFIG.get(component, []):
        if field in config and config[field]:
            continue
        if field == "options":
            config["options"] = _infer_prediction_options()
        elif field == "clue_text":
            config["clue_text"] = point.get("key_line") or point.get("highlight_reason") or "关键线索"
        elif field == "sides":
            config["sides"] = _infer_team_sides()
        repairs.append(f"G15: auto-filled config.{field} for {point.get('id')}")
    point["config"] = config
    return point


def _infer_prediction_options() -> list[dict[str, Any]]:
    return [{"text": "会发生", "is_correct": True}, {"text": "不会发生", "is_correct": False}]


def _infer_team_sides() -> list[dict[str, Any]]:
    return [{"label": "支持", "character": "主角"}, {"label": "反对", "character": "对手"}]


def _remove_overlaps(
    points: list[dict[str, Any]],
    warnings: list[str],
    *,
    min_gap_ms: int,
) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for point in points:
        if accepted and point["start_ms"] - accepted[-1]["end_ms"] < min_gap_ms:
            prev = accepted[-1]
            if point.get("priority", 0) > prev.get("priority", 0):
                warnings.append(f"G4: replaced close/overlapping {prev['id']} with {point['id']}")
                accepted[-1] = point
            else:
                warnings.append(f"G4: removed close/overlapping {point['id']}")
            continue
        accepted.append(point)
    return accepted


def _limit_points(
    points: list[dict[str, Any]],
    duration_ms: int,
    config: DesignConfig,
    repairs: list[str],
) -> list[dict[str, Any]]:
    max_allowed = config.max_points_for_duration(duration_ms)
    selected = points
    if len(selected) > max_allowed:
        selected = sorted(selected, key=lambda item: item.get("priority", 0), reverse=True)[:max_allowed]
        repairs.append(f"G6: truncated {len(points)} points to {max_allowed} by density config")
    max_total = config.max_total_interaction_ms(duration_ms)
    while max_total > 0 and len(selected) > config.min_points_per_episode and _total_duration(selected) > max_total:
        lowest = min(selected, key=lambda item: item.get("priority", 0))
        selected = [item for item in selected if item is not lowest]
        repairs.append(f"G8: removed {lowest['id']} to keep coverage below {config.max_coverage_ratio:.0%}")
    return sorted(selected, key=lambda item: item["start_ms"])


def _validate_final(points: list[dict[str, Any]], duration_ms: int, config: DesignConfig) -> list[str]:
    warnings: list[str] = []
    for point in points:
        duration = point["end_ms"] - point["start_ms"]
        if duration < config.min_duration_ms or duration > config.max_duration_ms:
            warnings.append(f"G1: {point['id']} duration={duration}ms out of configured bounds")
        if duration_ms > 0 and not (0 <= point["start_ms"] < point["end_ms"] <= duration_ms):
            warnings.append(f"G1: {point['id']} time out of bounds")
    for index in range(len(points) - 1):
        gap = points[index + 1]["start_ms"] - points[index]["end_ms"]
        if gap < config.min_gap_ms:
            warnings.append(f"G4: {points[index]['id']} too close to {points[index + 1]['id']}")
    max_allowed = config.max_points_for_duration(duration_ms)
    if len(points) > max_allowed:
        warnings.append(f"G6: {len(points)} points exceeds configured max {max_allowed}")
    if duration_ms > 0 and _total_duration(points) > config.max_total_interaction_ms(duration_ms):
        warnings.append("G8: total interaction duration exceeds configured coverage")
    components = {point.get("component") for point in points}
    if len(points) >= 3 and len(components) < config.min_unique_components:
        warnings.append("G7: only 1 component type used")
    return warnings


def _total_duration(points: list[dict[str, Any]]) -> int:
    return sum(point["end_ms"] - point["start_ms"] for point in points)


def _clamp(value: float) -> float:
    return max(0.0, min(value, 1.0))
