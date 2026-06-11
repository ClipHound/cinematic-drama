from __future__ import annotations

import json
from pathlib import Path
from typing import Any


EMOTION_TOKENS = (
    "放肆",
    "该死",
    "不可能",
    "怎么会",
    "你敢",
    "混账",
    "活该",
    "打得好",
    "喜欢",
    "救命",
    "不要",
)


def load_asr_segments(asr_path: Path) -> list[dict[str, Any]]:
    if not asr_path.exists():
        return []
    data = json.loads(asr_path.read_text(encoding="utf-8"))
    return list(data.get("segments") or [])


def extract_key_line(segments: list[dict[str, Any]], start_ms: int, end_ms: int) -> str:
    candidates = [
        segment
        for segment in segments
        if _segment_start(segment) <= end_ms and _segment_end(segment) >= start_ms
    ]
    if not candidates:
        return ""
    candidates.sort(key=_line_score, reverse=True)
    return str(candidates[0].get("text") or "").strip()


def _segment_start(segment: dict[str, Any]) -> int:
    return int(segment.get("start_ms") or segment.get("start") or 0)


def _segment_end(segment: dict[str, Any]) -> int:
    end = segment.get("end_ms") or segment.get("end")
    return int(end) if end is not None else _segment_start(segment)


def _line_score(segment: dict[str, Any]) -> tuple[int, int, int]:
    text = str(segment.get("text") or "")
    emotion_score = sum(1 for token in EMOTION_TOKENS if token in text)
    length_score = -abs(len(text) - 14)
    return emotion_score, length_score, _segment_start(segment)
