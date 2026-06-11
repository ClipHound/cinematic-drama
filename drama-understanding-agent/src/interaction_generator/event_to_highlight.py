from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from interaction_generator.config import KEYWORDS


@dataclass(slots=True)
class HighlightPoint:
    episode_num: int
    start_ms: int
    end_ms: int
    highlight_type: str
    description: str
    intensity: float
    confidence: float
    priority: float
    source_event_id: str = ""
    key_visual: str = ""
    reason_codes: list[str] = field(default_factory=list)


def events_to_highlights(
    events: list[dict[str, Any]],
    *,
    episode_num: int,
    episode_mood: str = "",
) -> list[HighlightPoint]:
    highlights = [
        event_to_highlight(event, episode_mood=episode_mood)
        for event in events
        if int(event.get("episode_num") or 0) == episode_num
    ]
    return sorted(highlights, key=lambda item: (item.start_ms, -item.priority))


def event_to_highlight(event: dict[str, Any], *, episode_mood: str = "") -> HighlightPoint:
    start_ms = parse_time_to_ms(str(event.get("start_time") or ""))
    raw_end = parse_time_to_ms(str(event.get("end_time") or ""))
    end_ms = raw_end if raw_end > start_ms else start_ms + 9000
    description = str(event.get("description") or "")
    event_type = str(event.get("event_type") or "")
    importance = _clamp(float(event.get("importance") or 0.5))
    highlight_type, reason_codes = classify_highlight(event_type, description, episode_mood)
    confidence = _clamp(0.55 + importance * 0.35 + _keyword_bonus(reason_codes))
    return HighlightPoint(
        episode_num=int(event.get("episode_num") or 0),
        start_ms=start_ms,
        end_ms=end_ms,
        highlight_type=highlight_type,
        description=description,
        intensity=importance,
        confidence=confidence,
        priority=_clamp(importance * 0.75 + confidence * 0.25),
        source_event_id=str(event.get("id") or ""),
        key_visual=description,
        reason_codes=reason_codes,
    )


def classify_highlight(
    event_type: str,
    description: str,
    episode_mood: str = "",
) -> tuple[str, list[str]]:
    matched = _keyword_matches(description)
    if event_type == "twist":
        return "reversal", matched or ["twist"]
    if event_type == "reveal":
        return "reveal", matched or ["reveal"]
    for preferred in ("sweet", "sad", "funny", "rescue", "face_slap", "anger"):
        if preferred in matched:
            return preferred, matched
    if event_type == "climax":
        return ("face_slap" if "anger" in matched else "reversal"), matched or ["high_impact"]
    if event_type == "conflict":
        return ("anger" if "anger" in matched else "conflict"), matched or ["conflict"]
    if event_type == "resolution":
        return ("success" if "success" in matched else "pressure"), matched or ["resolution"]
    mood_matches = _keyword_matches(episode_mood)
    if event_type == "setup":
        return "suspense", matched or mood_matches or ["setup"]
    return "conflict", matched or mood_matches or [event_type or "event"]


def parse_time_to_ms(value: str) -> int:
    text = value.strip()
    if not text:
        return 0
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return 0
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        return (numbers[0] * 60 + numbers[1]) * 1000
    if len(numbers) == 3:
        return (numbers[0] * 3600 + numbers[1] * 60 + numbers[2]) * 1000
    return 0


def _keyword_matches(text: str) -> list[str]:
    return [
        label
        for label, keywords in KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]


def _keyword_bonus(reason_codes: list[str]) -> float:
    return min(len(reason_codes) * 0.03, 0.12)


def _clamp(value: float) -> float:
    return max(0.0, min(value, 1.0))
