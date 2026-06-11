from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path

from django.conf import settings

from apps.catalog.models import Episode


THUMBNAIL_WIDTH = 160


def episode_video_path(episode: Episode) -> Path | None:
    if episode.video_file:
        path = Path(episode.video_file.path)
    elif episode.source_video_path:
        path = Path(episode.source_video_path)
    else:
        return None
    return path if path.is_file() else None


def ensure_episode_thumbnail(episode: Episode) -> Path | None:
    if episode.thumbnail:
        stored_path = Path(episode.thumbnail.path)
        if stored_path.is_file() and stored_path.stat().st_size > 0:
            return stored_path

    video_path = episode_video_path(episode)
    ffmpeg = shutil.which("ffmpeg")
    if video_path is None or ffmpeg is None:
        return None

    output_dir = settings.MEDIA_ROOT / "thumbnails" / episode.drama.slug
    output_path = output_dir / f"ep_{episode.episode_number:03d}.jpg"
    if output_path.is_file() and output_path.stat().st_size > 0:
        episode.thumbnail.name = output_path.relative_to(settings.MEDIA_ROOT).as_posix()
        episode.save(update_fields=["thumbnail", "updated_at"])
        return output_path

    output_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{os.getpid()}.{threading.get_ident()}.tmp.jpg"
    )
    temporary_path.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        "0",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={THUMBNAIL_WIDTH}:-2",
        "-q:v",
        "7",
        str(temporary_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=20)
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            return None
        temporary_path.replace(output_path)
        episode.thumbnail.name = output_path.relative_to(settings.MEDIA_ROOT).as_posix()
        episode.save(update_fields=["thumbnail", "updated_at"])
        return output_path
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        temporary_path.unlink(missing_ok=True)
