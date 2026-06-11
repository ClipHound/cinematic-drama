from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BranchNarrativeConfig:
    max_nodes: int = 25
    route_count: int = 3
    min_choices: int = 2
    max_choices: int = 3
    target_choice_depth: int = 4
    image_mode: str = "placeholder"
    version: str = "1.0"

