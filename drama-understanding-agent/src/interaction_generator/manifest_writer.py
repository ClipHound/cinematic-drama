from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from interaction_generator.config import MANIFEST_VERSION, SCHEMA_VERSION


def build_manifest(
    *,
    drama_id: str,
    episode_id: str,
    title: str,
    video_url: str,
    duration_ms: int,
    interaction_points: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "drama_id": drama_id,
        "episode_id": episode_id,
        "title": title,
        "source_video_url": video_url,
        "video_url": video_url,
        "video_duration_ms": duration_ms,
        "duration_ms": duration_ms,
        "manifest_version": MANIFEST_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "model_info": {
            "pipeline": "offline_video_understanding",
            "version": "interaction-generator-v1",
            "language": "zh-CN",
        },
        "interaction_points": interaction_points,
        "client_hints": {
            "asset_base_url": "/static/assets/",
            "ws_enabled": False,
            "tick_ms": 100,
        },
    }


def write_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{manifest['episode_id']}.interactions.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
