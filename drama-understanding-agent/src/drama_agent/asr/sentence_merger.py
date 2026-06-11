from __future__ import annotations

from typing import Any


END_PUNCTUATION = "。？！!?"
SOFT_PUNCTUATION = "，,；;：:、…"


def merge_to_sentences(
    segments: list[dict[str, Any]],
    vad_segments: list[dict[str, Any]] | None = None,
    *,
    max_gap_ms: int = 800,
    max_chars: int = 40,
) -> list[dict[str, Any]]:
    """Merge character/word-level ASR segments into prompt-friendly sentences."""
    normalized = [_normalize_segment(item) for item in segments if str(item.get("text") or "").strip()]
    if not normalized:
        return []
    speech_ranges = _speech_ranges(vad_segments or [])
    sentences: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    for segment in normalized:
        if current and _should_cut(current, segment, speech_ranges, max_gap_ms, max_chars):
            _append_sentence(sentences, current)
            current = []
        current.append(segment)

    if current:
        _append_sentence(sentences, current)
    return sentences


def _should_cut(
    current: list[dict[str, Any]],
    next_segment: dict[str, Any],
    speech_ranges: list[tuple[int, int]],
    max_gap_ms: int,
    max_chars: int,
) -> bool:
    prev = current[-1]
    text = "".join(item["text"] for item in current).strip()
    gap = next_segment["start_ms"] - prev["end_ms"]
    if speech_ranges and _vad_gap(prev["end_ms"], next_segment["start_ms"], speech_ranges) > max_gap_ms:
        return True
    if gap > max_gap_ms:
        return True
    if text.endswith(tuple(END_PUNCTUATION)):
        return True
    return len(text) >= max_chars or (len(text) >= 20 and text.endswith(tuple(SOFT_PUNCTUATION)))


def _append_sentence(sentences: list[dict[str, Any]], parts: list[dict[str, Any]]) -> None:
    text = "".join(item["text"] for item in parts).strip()
    if not text:
        return
    sentences.append(
        {
            "text": text,
            "start_ms": parts[0]["start_ms"],
            "end_ms": max(parts[-1]["end_ms"], parts[0]["start_ms"]),
        }
    )


def _normalize_segment(segment: dict[str, Any]) -> dict[str, Any]:
    start = int(segment.get("start_ms") or 0)
    end = int(segment.get("end_ms") or start)
    return {"text": str(segment.get("text") or ""), "start_ms": start, "end_ms": max(end, start)}


def _speech_ranges(vad_segments: list[dict[str, Any]]) -> list[tuple[int, int]]:
    ranges = []
    for item in vad_segments:
        if str(item.get("type") or "speech") != "speech":
            continue
        start = int(item.get("start_ms") or _seconds_to_ms(item.get("start_time")))
        end = int(item.get("end_ms") or _seconds_to_ms(item.get("end_time")))
        if end > start:
            ranges.append((start, end))
    return ranges


def _speech_index(value_ms: int, ranges: list[tuple[int, int]]) -> int | None:
    for index, (start, end) in enumerate(ranges):
        if start <= value_ms <= end:
            return index
    return None


def _vad_gap(left_ms: int, right_ms: int, ranges: list[tuple[int, int]]) -> int:
    left_index = _speech_index(left_ms, ranges)
    right_index = _speech_index(right_ms, ranges)
    if left_index is None or right_index is None or left_index == right_index:
        return 0
    return max(0, ranges[right_index][0] - ranges[left_index][1])


def _seconds_to_ms(value: Any) -> int:
    return int(float(value or 0) * 1000)
