from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_branch_package(package: dict[str, Any], output_dir: Path, drama_id: str) -> Path:
    target = output_dir / drama_id
    target.mkdir(parents=True, exist_ok=True)
    path = target / "branch_narrative.json"
    path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
