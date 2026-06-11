from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from drama_agent.asr.sentence_merger import merge_to_sentences


@dataclass(slots=True)
class ASRResult:
    text: str = ""
    language: str = "Chinese"
    segments: list[dict[str, Any]] = field(default_factory=list)
    sentences: list[dict[str, Any]] = field(default_factory=list)
    vad_segments: list[dict[str, Any]] = field(default_factory=list)
    emotion_segments: list[dict[str, Any]] = field(default_factory=list)
    audio_events: list[dict[str, Any]] = field(default_factory=list)
    asr_available: bool = True
    error: str = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "segments": self.segments,
            "sentences": self.sentences,
            "vad_segments": self.vad_segments,
            "emotion_segments": self.emotion_segments,
            "audio_events": self.audio_events,
            "asr_available": self.asr_available,
            "error": self.error,
        }


class ASRClient:
    def __init__(self, endpoint: str = "", *, timeout: float = 180.0):
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.endpoint)

    def transcribe(self, video_path: Path) -> ASRResult:
        if not self.enabled:
            return ASRResult(asr_available=False, error="ASR endpoint is not configured")
        try:
            with video_path.open("rb") as fh:
                response = httpx.post(
                    self._transcribe_url(),
                    data={
                        "language": "Chinese",
                        "include_timestamps": "true",
                        "include_vad": "true",
                        "include_emotion": "true",
                    },
                    files={"file": (video_path.name, fh, "video/mp4")},
                    timeout=self.timeout,
                )
            response.raise_for_status()
            return normalize_asr_response(response.json())
        except Exception as exc:
            return ASRResult(asr_available=False, error=str(exc))

    def _transcribe_url(self) -> str:
        if self.endpoint.endswith(("/transcribe", "/audio/transcriptions")):
            return self.endpoint
        return f"{self.endpoint}/transcribe"


def normalize_asr_response(data: dict[str, Any]) -> ASRResult:
    segments = data.get("segments") or data.get("time_stamps") or []
    normalized_segments = [_normalize_segment(item) for item in segments]
    vad_segments = list(data.get("vad_segments") or [])
    return ASRResult(
        text=str(data.get("text") or _join_segments(normalized_segments)),
        language=str(data.get("language") or "Chinese"),
        segments=normalized_segments,
        sentences=merge_to_sentences(normalized_segments, vad_segments),
        vad_segments=vad_segments,
        emotion_segments=list(data.get("emotion_segments") or []),
        audio_events=list(data.get("audio_events") or []),
        asr_available=True,
    )


def format_asr_for_prompt(data: dict[str, Any]) -> str:
    if not data.get("asr_available", True):
        return "(ASR unavailable)"
    segments = data.get("sentences") or merge_to_sentences(data.get("segments") or [], data.get("vad_segments") or [])
    if not segments:
        return data.get("text") or "(none)"
    lines = ["## Current Episode ASR (timestamped)"]
    emotions = data.get("emotion_segments") or []
    for segment in segments:
        start = int(segment.get("start_ms") or 0)
        end = int(segment.get("end_ms") or start)
        tag = _emotion_tag(emotions, start, end)
        suffix = f"  [{tag}]" if tag else ""
        lines.append(f"[{format_ms_precise(start)}-{format_ms_precise(end)}] {segment.get('text', '')}{suffix}")
    return "\n".join(lines)


def read_asr_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_segment(segment: dict[str, Any]) -> dict[str, Any]:
    start = _segment_time_to_ms(segment, "start")
    end = _segment_time_to_ms(segment, "end", default=start)
    return {
        "text": str(segment.get("text") or ""),
        "start_ms": start,
        "end_ms": end,
    }


def _segment_time_to_ms(segment: dict[str, Any], prefix: str, *, default: int = 0) -> int:
    ms_key = f"{prefix}_ms"
    time_key = f"{prefix}_time"
    if ms_key in segment:
        return int(float(segment.get(ms_key) or default))
    if time_key in segment:
        return _to_ms(segment.get(time_key))
    if prefix in segment:
        return _to_ms(segment.get(prefix))
    return default


def _to_ms(value: Any) -> int:
    number = float(value or 0)
    return int(number * 1000) if number < 10000 else int(number)


def _join_segments(segments: list[dict[str, Any]]) -> str:
    return "".join(str(segment.get("text") or "") for segment in segments)


def _emotion_tag(emotions: list[dict[str, Any]], start_ms: int, end_ms: int) -> str:
    for item in emotions:
        left = int(item.get("start_ms") or 0)
        right = int(item.get("end_ms") or left)
        if left <= end_ms and right >= start_ms:
            return f"emotion:{item.get('emotion', '')}@{float(item.get('score') or 0):.2f}"
    return ""


def format_ms_precise(value_ms: int) -> str:
    total = value_ms / 1000
    minutes = int(total // 60)
    seconds = total - minutes * 60
    return f"{minutes:02d}:{seconds:06.3f}"
