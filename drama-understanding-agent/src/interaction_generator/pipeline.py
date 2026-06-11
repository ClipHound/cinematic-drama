from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from interaction_generator.asr_analyzer import extract_key_line, load_asr_segments
from interaction_generator.config import MIN_CONFIDENCE, MIN_GAP_MS
from interaction_generator.event_to_highlight import HighlightPoint, events_to_highlights
from interaction_generator.highlight_to_ip import highlight_to_interaction_point
from interaction_generator.manifest_writer import build_manifest, write_manifest


@dataclass(slots=True)
class GenerationResult:
    episode_num: int
    manifest_path: Path
    interaction_count: int


def generate_interaction_manifests(
    *,
    project_dir: Path,
    output_dir: Path,
    drama_id: str | None = None,
    video_base_url: str = "",
    video_dir: Path | None = None,
    video_pattern: str = "ep{num:02d}.mp4",
) -> list[GenerationResult]:
    report = _load_report(project_dir)
    metadata = _load_metadata(project_dir)
    resolved_drama_id = drama_id or report.get("project_id") or metadata.get("project_id") or "drama"
    episode_nums = sorted({int(event["episode_num"]) for event in report.get("plot_events", [])})
    results: list[GenerationResult] = []
    for episode_num in episode_nums:
        manifest = generate_episode_manifest(
            report=report,
            project_dir=project_dir,
            drama_id=str(resolved_drama_id),
            episode_num=episode_num,
            video_base_url=video_base_url,
            video_dir=video_dir,
            video_pattern=video_pattern,
        )
        path = write_manifest(manifest, output_dir / str(resolved_drama_id))
        results.append(
            GenerationResult(
                episode_num=episode_num,
                manifest_path=path,
                interaction_count=len(manifest["interaction_points"]),
            )
        )
    return results


def generate_episode_manifest(
    *,
    report: dict[str, Any],
    project_dir: Path,
    drama_id: str,
    episode_num: int,
    video_base_url: str = "",
    video_dir: Path | None = None,
    video_pattern: str = "ep{num:02d}.mp4",
) -> dict[str, Any]:
    episode_id = f"ep_{episode_num:03d}"
    episode_events = [
        event for event in report.get("plot_events", []) if int(event.get("episode_num") or 0) == episode_num
    ]
    duration_ms = _episode_duration_ms(episode_events, video_dir, video_pattern, episode_num)
    mood = _episode_summary(report, episode_num).get("mood", "")
    highlights = _quality_gate(
        events_to_highlights(episode_events, episode_num=episode_num, episode_mood=mood)
    )
    segments = load_asr_segments(project_dir / "asr" / f"ep{episode_num:02d}.json")
    points = [
        highlight_to_interaction_point(
            highlight,
            episode_id=episode_id,
            index=index,
            duration_ms=duration_ms,
            key_line=extract_key_line(segments, highlight.start_ms, highlight.end_ms),
        )
        for index, highlight in enumerate(highlights, start=1)
    ]
    points.extend(_episode_end_points(report, episode_num, episode_id, duration_ms, len(points) + 1))
    return build_manifest(
        drama_id=drama_id,
        episode_id=episode_id,
        title=f"第 {episode_num} 集",
        video_url=_video_url(video_base_url, video_pattern, episode_num),
        duration_ms=duration_ms,
        interaction_points=points,
    )


def _episode_end_points(
    report: dict[str, Any],
    episode_num: int,
    episode_id: str,
    duration_ms: int,
    start_index: int,
) -> list[dict[str, Any]]:
    summary = _episode_summary(report, episode_num)
    cliffhanger = str(summary.get("cliffhanger") or "")
    if not cliffhanger or duration_ms <= 0:
        return []
    highlight = HighlightPoint(
        episode_num=episode_num,
        start_ms=max(duration_ms - 9000, 0),
        end_ms=max(duration_ms - 1000, 1000),
        highlight_type="cliffhanger",
        description=cliffhanger,
        intensity=0.88,
        confidence=0.9,
        priority=0.95,
        reason_codes=["cliffhanger", "episode_end"],
    )
    point = highlight_to_interaction_point(
        highlight,
        episode_id=episode_id,
        index=start_index,
        duration_ms=duration_ms,
    )
    point["config"].update(
        {
            "question": "下一集最可能发生什么？",
            "options": [
                {"option_key": "reveal", "label": "身份被揭开"},
                {"option_key": "test", "label": "实力被试探"},
            ],
            "reveal_episode_id": f"ep_{episode_num + 1:03d}",
        }
    )
    return [point]


def _quality_gate(highlights: list[HighlightPoint]) -> list[HighlightPoint]:
    accepted: list[HighlightPoint] = []
    for highlight in sorted(highlights, key=lambda item: (-item.priority, item.start_ms)):
        if highlight.confidence < MIN_CONFIDENCE:
            continue
        if any(abs(highlight.start_ms - item.start_ms) < MIN_GAP_MS for item in accepted):
            continue
        accepted.append(highlight)
    return sorted(accepted, key=lambda item: item.start_ms)


def _episode_duration_ms(
    events: list[dict[str, Any]],
    video_dir: Path | None,
    video_pattern: str,
    episode_num: int,
) -> int:
    if video_dir is not None:
        duration = _ffprobe_duration_ms(video_dir / video_pattern.format(num=episode_num))
        if duration > 0:
            return duration
    max_event_end = 0
    for event in events:
        from interaction_generator.event_to_highlight import parse_time_to_ms

        max_event_end = max(max_event_end, parse_time_to_ms(str(event.get("end_time") or "")))
    return max_event_end + 12000 if max_event_end else 0


def _ffprobe_duration_ms(video_path: Path) -> int:
    if not video_path.exists():
        return 0
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        return int(float(result.stdout.strip()) * 1000) if result.returncode == 0 else 0
    except Exception:
        return 0


def _load_report(project_dir: Path) -> dict[str, Any]:
    return json.loads((project_dir / "output" / "report.json").read_text(encoding="utf-8"))


def _load_metadata(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "project.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _episode_summary(report: dict[str, Any], episode_num: int) -> dict[str, Any]:
    for summary in report.get("episode_summaries", []):
        if int(summary.get("episode_num") or 0) == episode_num:
            return summary
    return {}


def _video_url(video_base_url: str, video_pattern: str, episode_num: int) -> str:
    filename = video_pattern.format(num=episode_num)
    if not video_base_url:
        return filename
    return f"{video_base_url.rstrip('/')}/{filename}"
