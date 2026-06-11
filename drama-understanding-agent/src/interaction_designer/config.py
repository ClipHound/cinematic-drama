from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(slots=True)
class DesignConfig:
    max_points_per_minute: float = 1.5
    min_points_per_episode: int = 2
    max_points_per_episode: int = 8
    max_coverage_ratio: float = 0.35
    min_gap_ms: int = 10000
    min_duration_ms: int = 5000
    max_duration_ms: int = 20000
    max_consecutive_same_component: int = 2
    min_unique_components: int = 2

    @classmethod
    def from_file(cls, path: str | Path | None) -> "DesignConfig":
        if path is None:
            return cls()
        config_path = Path(path)
        if not config_path.exists():
            return cls()
        allowed = {field.name for field in fields(cls)}
        overrides = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(**{key: value for key, value in overrides.items() if key in allowed})

    def max_points_for_duration(self, duration_ms: int) -> int:
        if duration_ms <= 0:
            return self.max_points_per_episode
        minutes = duration_ms / 60000
        by_rate = int(minutes * self.max_points_per_minute)
        return max(self.min_points_per_episode, min(by_rate, self.max_points_per_episode))

    def max_total_interaction_ms(self, duration_ms: int) -> int:
        return int(max(duration_ms, 0) * self.max_coverage_ratio)
