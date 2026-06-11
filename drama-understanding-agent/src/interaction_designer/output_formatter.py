from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from interaction_designer.manifest_writer import build_manifest, write_manifest


def write_episode_design(
    *,
    design: dict[str, Any],
    drama_id: str,
    episode_num: int,
    output_dir: Path,
    video_base_url: str = "",
    video_dir: Path | None = None,
    video_pattern: str = "ep{num:02d}.mp4",
    asr_data: dict[str, Any] | None = None,
) -> Path:
    episode_id = f"ep_{episode_num:03d}"
    duration_ms = infer_duration_ms(video_dir, video_pattern, episode_num, design, asr_data=asr_data)
    manifest = build_manifest(
        drama_id=drama_id,
        episode_id=episode_id,
        title=f"第 {episode_num} 集",
        video_url=_video_url(video_base_url, video_pattern, episode_num),
        duration_ms=duration_ms,
        interaction_points=design.get("interaction_points") or [],
    )
    manifest["episode_end_interaction"] = design.get("episode_end_interaction") or {}
    manifest["design_notes"] = design.get("design_notes", "")
    manifest["design_warnings"] = design.get("warnings", [])
    manifest["design_repairs"] = design.get("repair_notes", [])
    return write_manifest(manifest, output_dir / drama_id)


def infer_duration_ms(
    video_dir: Path | None,
    video_pattern: str,
    episode_num: int,
    design: dict[str, Any],
    *,
    asr_data: dict[str, Any] | None = None,
) -> int:
    if video_dir is not None:
        duration = _ffprobe_duration_ms(video_dir / video_pattern.format(num=episode_num))
        if duration > 0:
            return duration
    if asr_data and int(asr_data.get("vad_end_ms") or 0) > 0:
        return int(asr_data["vad_end_ms"]) + 5000
    if asr_data and asr_data.get("vad_segments"):
        vad_end = max((int(item.get("end_ms") or 0) for item in asr_data["vad_segments"]), default=0)
        if vad_end > 0:
            return vad_end + 5000
    max_end = max((int(p.get("end_ms") or 0) for p in design.get("interaction_points") or []), default=0)
    return max_end + 12000 if max_end else 0


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


def _video_url(video_base_url: str, video_pattern: str, episode_num: int) -> str:
    filename = video_pattern.format(num=episode_num)
    return f"{video_base_url.rstrip('/')}/{filename}" if video_base_url else filename
