from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from drama_agent.config import RunMode, Settings
from drama_agent.memory.schemas import utc_now


class ProjectMetadata(BaseModel):
    project_id: str
    drama_title: str
    total_episodes: int
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


@dataclass(slots=True)
class ProjectConfig:
    project_id: str
    drama_title: str
    video_dir: Path
    video_pattern: str
    total_episodes: int
    output_dir: Path
    model_endpoint: str
    model_token: str
    model_name: str
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    embed_endpoint: str = "http://localhost:11434"
    embed_model: str = "qwen3-embedding:0.6b"
    asr_endpoint: str = ""
    start_episode: int = 1
    mode: RunMode = "full_auto"

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        project_id: str,
        drama_title: str,
        video_dir: Path,
        video_pattern: str,
        total_episodes: int,
        output_dir: Path | None = None,
        start_episode: int = 1,
    ) -> "ProjectConfig":
        root = output_dir or settings.projects_root / project_id
        return cls(
            project_id=project_id,
            drama_title=drama_title,
            video_dir=video_dir,
            video_pattern=video_pattern,
            total_episodes=total_episodes,
            output_dir=root,
            model_endpoint=settings.model_endpoint,
            model_token=settings.model_token,
            model_name=settings.model_name,
            qdrant_host=settings.qdrant_host,
            qdrant_port=settings.qdrant_port,
            embed_endpoint=settings.embed_endpoint,
            embed_model=settings.embed_model,
            asr_endpoint=settings.asr_endpoint,
            start_episode=start_episode,
            mode=settings.mode,
        )


class Project:
    """Owns the physical project boundary on disk."""

    def __init__(self, config: ProjectConfig):
        self.config = config
        self.root = config.output_dir

    @property
    def db_path(self) -> Path:
        return self.root / "memory.db"

    @property
    def metadata_path(self) -> Path:
        return self.root / "project.json"

    @property
    def qdrant_path(self) -> Path:
        return self.root / "qdrant"

    def initialize(self) -> None:
        for path in (
            self.root,
            self.root / "episodes",
            self.root / "asr",
            self.root / "assets" / "characters",
            self.root / "assets" / "evidence",
            self.root / "assets" / "frames",
            self.root / "snapshots",
            self.root / "action_plans",
            self.root / "patches",
            self.root / "logs" / "patches",
            self.root / "output" / "knowledge_base",
            self.qdrant_path,
        ):
            path.mkdir(parents=True, exist_ok=True)

        if self.metadata_path.exists():
            metadata = ProjectMetadata.model_validate_json(
                self.metadata_path.read_text(encoding="utf-8")
            )
            metadata.updated_at = utc_now()
        else:
            metadata = ProjectMetadata(
                project_id=self.config.project_id,
                drama_title=self.config.drama_title,
                total_episodes=self.config.total_episodes,
            )
        self.write_json(self.metadata_path, metadata.model_dump())

    def create_snapshot(self, episode_num: int) -> Path:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Cannot snapshot missing database: {self.db_path}")
        snapshot_path = self.snapshot_path(episode_num)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.db_path, snapshot_path)
        return snapshot_path

    def restore_snapshot(self, episode_num: int) -> Path:
        snapshot_path = self.snapshot_path(episode_num)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")
        shutil.copy2(snapshot_path, self.db_path)
        return self.db_path

    def snapshot_path(self, episode_num: int) -> Path:
        return self.root / "snapshots" / f"after_ep{episode_num:02d}.db"

    def episode_video_path(self, episode_num: int) -> Path:
        filename = self.config.video_pattern.format(num=episode_num)
        return self.config.video_dir / filename

    def write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
