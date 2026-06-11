from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class EpisodeContext:
    episode_num: int
    video_path: Path
    asr_text: str = ""
    known_characters: list[dict[str, Any]] = field(default_factory=list)
    open_threads: list[dict[str, Any]] = field(default_factory=list)
    previous_summary: str = ""
    series_state: dict[str, Any] = field(default_factory=dict)
    project_root: Path | None = None
    character_name_map: dict[str, str] = field(default_factory=dict)
    relationship_key_map: dict[str, str] = field(default_factory=dict)
    thread_title_map: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutionResult:
    episode_num: int
    summary: str = ""
    actions_total: int = 0
    actions_succeeded: int = 0
    actions_failed: int = 0
    patches_generated: int = 0
    patches_committed: int = 0
    patches_flagged: int = 0
    uncertainties: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_sec: float = 0.0
    candidate_interactions: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_critical_error(self) -> bool:
        return self.actions_total == 0 and bool(self.errors)
