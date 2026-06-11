from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Choice:
    choice_id: str
    option_text: str
    option_subtext: str
    leads_to: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "choice_id": self.choice_id,
            "option_text": self.option_text,
            "option_subtext": self.option_subtext,
            "leads_to": self.leads_to,
        }


@dataclass(slots=True)
class BranchNode:
    node_id: str
    layer: int
    route_tag: str
    narrative: dict[str, Any]
    visual: dict[str, Any] = field(default_factory=dict)
    choices: list[Choice] = field(default_factory=list)
    audio_hint: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "layer": self.layer,
            "route_tag": self.route_tag,
            "narrative": self.narrative,
            "visual": self.visual,
            "choices": [choice.model_dump() for choice in self.choices],
            "audio_hint": self.audio_hint,
        }


@dataclass(slots=True)
class BranchEnding:
    ending_id: str
    ending_title: str
    ending_subtitle: str
    narrative: dict[str, Any]
    visual: dict[str, Any]
    epilogue: str
    character_fates: dict[str, str]

    def model_dump(self) -> dict[str, Any]:
        return {
            "ending_id": self.ending_id,
            "ending_title": self.ending_title,
            "ending_subtitle": self.ending_subtitle,
            "narrative": self.narrative,
            "visual": self.visual,
            "epilogue": self.epilogue,
            "character_fates": self.character_fates,
        }

