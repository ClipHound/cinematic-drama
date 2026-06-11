from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class Character(BaseModel):
    id: str = Field(default_factory=lambda: new_id("char"))
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    first_seen: int
    last_seen: int = 0
    status: Literal["active", "dead", "unknown", "merged"] = "active"
    merged_into: str | None = None
    confidence: float = 1.0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class CharacterState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("state"))
    character_id: str
    episode_num: int
    emotion: str = ""
    goal: str = ""
    identity: str = ""
    appearance: str = ""
    notes: str = ""
    created_at: str = Field(default_factory=utc_now)


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rel"))
    character_a: str
    character_b: str
    relation: str
    direction: Literal["a_to_b", "b_to_a", "bidirectional"] = "bidirectional"
    established: int
    ended: int | None = None
    confidence: float = 1.0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class PlotEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("event"))
    episode_num: int
    start_time: str = ""
    end_time: str = ""
    event_type: Literal["setup", "conflict", "climax", "resolution", "reveal", "twist"]
    description: str
    characters: list[str] = Field(default_factory=list)
    importance: float = 0.5
    created_at: str = Field(default_factory=utc_now)


class PlotThread(BaseModel):
    id: str = Field(default_factory=lambda: new_id("thread"))
    title: str
    description: str
    thread_type: Literal["foreshadow", "mystery", "subplot", "mainplot"] = "foreshadow"
    status: Literal["open", "resolved", "abandoned"] = "open"
    opened_at: int
    resolved_at: int | None = None
    resolution: str = ""
    characters: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class EpisodeSummary(BaseModel):
    episode_num: int
    summary: str
    key_events: list[str] = Field(default_factory=list)
    mood: str = ""
    cliffhanger: str = ""
    created_at: str = Field(default_factory=utc_now)


class SeriesState(BaseModel):
    id: int = 1
    current_episode: int = 0
    total_episodes: int = 0
    main_plot_summary: str = ""
    genre: str = ""
    setting: str = ""
    tone: str = ""
    updated_at: str = Field(default_factory=utc_now)


class CharacterAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("asset"))
    character_id: str
    asset_type: Literal["anchor", "reference", "costume"]
    file_path: str
    episode_num: int
    timestamp: str = ""
    description: str = ""
    created_at: str = Field(default_factory=utc_now)


class EvidenceAsset(BaseModel):
    id: str = Field(default_factory=lambda: new_id("evidence"))
    episode_num: int
    asset_type: str
    file_path: str
    description: str
    related_thread: str | None = None
    timestamp: str = ""
    created_at: str = Field(default_factory=utc_now)


class StatePatch(BaseModel):
    id: str = Field(default_factory=lambda: new_id("patch"))
    episode_num: int
    table: str
    operation: Literal["insert", "update", "delete"]
    record_id: str
    field_changes: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    reason: str = ""
    source_action: str = ""
    conflicts: list[str] = Field(default_factory=list)


class CommitResult(BaseModel):
    episode_num: int
    patches_total: int = 0
    patches_committed: int = 0
    patches_flagged: int = 0
    errors: list[str] = Field(default_factory=list)


class OperationLog(BaseModel):
    episode_num: int
    action_type: str
    action_data: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    created_at: str = Field(default_factory=utc_now)
