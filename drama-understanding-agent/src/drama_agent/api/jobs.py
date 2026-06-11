from __future__ import annotations

import traceback
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable


@dataclass(slots=True)
class Job:
    id: str
    kind: str
    status: str
    created_at: str
    updated_at: str
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None
    logs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "request": self.request,
            "result": self.result,
            "error": self.error,
            "logs": self.logs[-50:],
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def start(self, kind: str, request: dict[str, Any], target: Callable[[dict[str, Any], Job], dict[str, Any]]) -> Job:
        now = _now()
        job = Job(
            id=uuid.uuid4().hex,
            kind=kind,
            status="queued",
            created_at=now,
            updated_at=now,
            request=request,
        )
        with self._lock:
            self._jobs[job.id] = job

        thread = Thread(target=self._run, args=(job.id, target), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def _run(self, job_id: str, target: Callable[[dict[str, Any], Job], dict[str, Any]]) -> None:
        job = self.get(job_id)
        if job is None:
            return
        self._set(job, status="running")
        try:
            result = target(job.request, job)
            self._set(job, status="succeeded", result=result)
        except Exception as exc:
            self._set(job, status="failed", error=f"{exc}\n{traceback.format_exc()}")

    def _set(
        self,
        job: Job,
        *,
        status: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if status:
                job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = _now()


def run_understanding(payload: dict[str, Any], job: Job) -> dict[str, Any]:
    from drama_agent.config import load_settings
    from drama_agent.engine.episode_loop import EpisodeLoop
    from drama_agent.project import ProjectConfig

    settings = load_settings()
    title = str(payload["title"])
    video_dir = Path(str(payload["video_dir"]))
    episodes = int(payload["episodes"])
    pattern = str(payload.get("pattern") or "ep{num:02d}.mp4")
    project_id = payload.get("project_id")
    output_dir = Path(str(payload["output_dir"])) if payload.get("output_dir") else None
    from_episode = int(payload.get("from_episode") or 1)
    job.logs.append(f"understanding start: {title}, episodes={episodes}")
    config = ProjectConfig.from_settings(
        settings,
        project_id=str(project_id) if project_id else None,
        drama_title=title,
        video_dir=video_dir,
        video_pattern=pattern,
        total_episodes=episodes,
        output_dir=output_dir,
        start_episode=from_episode,
    )
    result = EpisodeLoop(config).run()
    return {"project": str(config.output_dir), "result": result}


def run_interaction_design(payload: dict[str, Any], job: Job) -> dict[str, Any]:
    from drama_agent.config import load_settings
    from interaction_designer.agent import InteractionDesignAgent
    from interaction_designer.config import DesignConfig
    from interaction_designer.llm import TextLLM

    settings = load_settings()
    project = Path(str(payload["project"]))
    output_dir = Path(str(payload.get("output_dir") or "outputs"))
    drama_id = payload.get("drama_id")
    video_base_url = str(payload.get("video_base_url") or "")
    video_dir = Path(str(payload["video_dir"])) if payload.get("video_dir") else None
    pattern = str(payload.get("pattern") or "ep{num:02d}.mp4")
    blueprint = Path(str(payload["blueprint"])) if payload.get("blueprint") else None
    config_path = Path(str(payload["config"])) if payload.get("config") else None
    job.logs.append(f"interaction design start: project={project}")
    llm = TextLLM(
        settings.model_endpoint,
        settings.model_token,
        settings.model_name,
        timeout=settings.request_timeout_sec,
    )
    results = InteractionDesignAgent(llm).run(
        project_dir=project,
        output_dir=output_dir,
        drama_id=str(drama_id) if drama_id else None,
        video_base_url=video_base_url,
        video_dir=video_dir,
        video_pattern=pattern,
        blueprint_path=blueprint,
        design_config=DesignConfig.from_file(config_path),
    )
    return {
        "episodes": [
            {
                "episodeNumber": result.episode_num,
                "interactionCount": result.interaction_count,
                "manifestPath": str(result.manifest_path),
            }
            for result in results
        ]
    }


def run_recreation(payload: dict[str, Any], job: Job) -> dict[str, Any]:
    from branch_narrative.agent import BranchNarrativeAgent
    from branch_narrative.config import BranchNarrativeConfig
    from drama_agent.config import load_settings
    from interaction_designer.llm import TextLLM

    settings = load_settings()
    project = Path(str(payload["project"]))
    output_dir = Path(str(payload.get("output_dir") or "outputs"))
    interactions_dir = Path(str(payload["interactions_dir"])) if payload.get("interactions_dir") else None
    drama_id = payload.get("drama_id")
    image_mode = str(payload.get("image_mode") or "placeholder")
    job.logs.append(f"recreation start: project={project}")
    llm = TextLLM(
        settings.model_endpoint,
        settings.model_token,
        settings.model_name,
        timeout=settings.request_timeout_sec,
    )
    result = BranchNarrativeAgent(llm, BranchNarrativeConfig(image_mode=image_mode)).run(
        project_dir=project,
        output_dir=output_dir,
        drama_id=str(drama_id) if drama_id else None,
        interactions_dir=interactions_dir,
    )
    return {
        "packagePath": str(result.package_path),
        "totalNodes": result.total_nodes,
        "endingsCount": result.endings_count,
        "warnings": result.warnings,
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()
