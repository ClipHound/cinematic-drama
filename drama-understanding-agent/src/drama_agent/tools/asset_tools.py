from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.memory.schemas import CharacterAsset, EvidenceAsset, StatePatch
from drama_agent.memory.store import MemoryStore
from drama_agent.tools.utils import find_character_fuzzy


def handle_capture_frame(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    if ctx.project_root is None:
        return []
    timestamp = action.get("timestamp", "00:00")
    purpose = action.get("purpose", "key_scene")
    safe_target = _safe_name(action.get("target") or purpose)
    out_dir = ctx.project_root / "assets" / ("characters" if purpose == "character_anchor" else "evidence")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ep{ctx.episode_num:02d}_{safe_target}_{timestamp.replace(':', '')}.jpg"

    _ffmpeg_capture(ctx.video_path, timestamp, out_path)
    rel_path = str(out_path.relative_to(ctx.project_root / "assets"))

    if purpose == "character_anchor":
        character = find_character_fuzzy(memory, action.get("target", ""))
        if not character:
            return []
        asset = CharacterAsset(
            character_id=character.id,
            asset_type="anchor",
            file_path=rel_path,
            episode_num=ctx.episode_num,
            timestamp=timestamp,
            description=action.get("description", ""),
        )
        return [
            StatePatch(
                episode_num=ctx.episode_num,
                table="character_assets",
                operation="insert",
                record_id=asset.id,
                field_changes=asset.model_dump(),
                confidence=0.9,
                reason="Captured character anchor frame",
                source_action="capture_frame",
            )
        ]

    asset = EvidenceAsset(
        episode_num=ctx.episode_num,
        asset_type=purpose,
        file_path=rel_path,
        description=action.get("description", ""),
        timestamp=timestamp,
    )
    return [
        StatePatch(
            episode_num=ctx.episode_num,
            table="evidence_assets",
            operation="insert",
            record_id=asset.id,
            field_changes=asset.model_dump(),
            confidence=0.9,
            reason="Captured evidence frame",
            source_action="capture_frame",
        )
    ]


def _ffmpeg_capture(video_path: Path, timestamp: str, out_path: Path) -> None:
    result = _run_ffmpeg_capture(video_path, timestamp, out_path)
    if result.returncode == 0:
        return
    retry_timestamp = _shift_timestamp(timestamp, -1)
    if retry_timestamp != timestamp:
        result = _run_ffmpeg_capture(video_path, retry_timestamp, out_path)
        if result.returncode == 0:
            return
    raise RuntimeError(f"ffmpeg capture frame failed: {result.stderr}")


def _run_ffmpeg_capture(video_path: Path, timestamp: str, out_path: Path) -> subprocess.CompletedProcess:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        timestamp,
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(out_path),
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _shift_timestamp(timestamp: str, delta_sec: int) -> str:
    parts = [int(part) for part in timestamp.split(":") if part.isdigit()]
    if len(parts) == 2:
        total = parts[0] * 60 + parts[1] + delta_sec
    elif len(parts) == 3:
        total = parts[0] * 3600 + parts[1] * 60 + parts[2] + delta_sec
    else:
        return timestamp
    total = max(total, 0)
    return f"{total // 60:02d}:{total % 60:02d}"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value).strip("_")[:40] or "frame"
