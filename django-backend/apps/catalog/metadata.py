from __future__ import annotations

from pathlib import Path
from shutil import copy2

POSTER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def imported_poster_name(media_root: Path, slug: str, title: str, asset_root: Path | None = None) -> str:
    poster_dir = media_root / "posters"
    for extension in POSTER_EXTENSIONS:
        candidate = poster_dir / f"{slug}{extension}"
        if candidate.is_file():
            return candidate.relative_to(media_root).as_posix()

    if asset_root is not None:
        for extension in POSTER_EXTENSIONS:
            for stem in (slug, title):
                source = asset_root / "posters" / f"{stem}{extension}"
                if not source.is_file():
                    continue
                poster_dir.mkdir(parents=True, exist_ok=True)
                destination = poster_dir / f"{slug}{extension}"
                copy2(source, destination)
                return destination.relative_to(media_root).as_posix()
    return ""
