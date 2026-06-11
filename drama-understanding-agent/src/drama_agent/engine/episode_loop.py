from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from drama_agent.asr.client import ASRClient, format_asr_for_prompt, read_asr_file
from drama_agent.engine.action_plan import ActionPlanEngine, parse_action_plan
from drama_agent.engine.episode_types import EpisodeContext, ExecutionResult
from drama_agent.engine.reporting import render_markdown_report
from drama_agent.engine.state_patch import PatchCommitter
from drama_agent.memory.schemas import EpisodeSummary
from drama_agent.memory.store import MemoryStore
from drama_agent.memory.vectors import VectorStore
from drama_agent.model.client import DoubaoClient
from drama_agent.model.prompts import SYSTEM_PROMPT, build_episode_prompt
from drama_agent.project import Project, ProjectConfig


class EpisodeModel(Protocol):
    def understand_episode(self, video_path: Path, episode_prompt: str, system_prompt: str) -> str:
        ...


class EpisodeLoop:
    def __init__(
        self,
        config: ProjectConfig,
        *,
        model: EpisodeModel | None = None,
        memory: MemoryStore | None = None,
        vectors: VectorStore | None = None,
    ):
        self.config = config
        self.project = Project(config)
        self.memory = memory or MemoryStore(self.project.db_path)
        self.vectors = vectors or VectorStore(
            project_id=config.project_id,
            qdrant_path=self.project.qdrant_path,
            host=config.qdrant_host,
            port=config.qdrant_port,
            embed_endpoint=config.embed_endpoint,
            embed_model=config.embed_model,
        )
        self.model = model or DoubaoClient(
            config.model_endpoint,
            config.model_token,
            config.model_name,
        )
        self.asr = ASRClient(config.asr_endpoint)
        self.engine = ActionPlanEngine(self.memory)
        self.committer = PatchCommitter(
            self.memory,
            self.vectors,
            patch_log_dir=self.project.root / "logs" / "patches",
        )

    def run(self) -> dict[str, Any]:
        self.project.initialize()
        self.memory.update_series_state(total_episodes=self.config.total_episodes)
        start = self._determine_start_episode()
        self._batch_asr(start, self.config.total_episodes)
        results: list[ExecutionResult] = []
        failures = 0

        for episode_num in range(start, self.config.total_episodes + 1):
            result = self.process_episode(episode_num)
            results.append(result)
            if result.errors:
                failures += 1
            else:
                failures = 0
            if failures >= 3:
                break

        return self.generate_final_report(results)

    def process_episode(self, episode_num: int) -> ExecutionResult:
        self._ensure_asr(episode_num)
        ctx = self.build_context(episode_num)
        prompt = build_episode_prompt(ctx, self.config.drama_title, self.config.total_episodes)
        raw_response = self.model.understand_episode(ctx.video_path, prompt, SYSTEM_PROMPT)
        plan = parse_action_plan(raw_response)
        self._write_action_plan(episode_num, plan)
        if "_error" in plan:
            return ExecutionResult(
                episode_num=episode_num,
                errors=[f"Action plan parse failed: {plan.get('raw', '')[:120]}"],
            )

        result, patches = self.engine.execute(plan, ctx)
        commit = self.committer.commit_episode_patches(patches)
        result.patches_committed = commit.patches_committed
        result.patches_flagged = commit.patches_flagged
        result.errors.extend(commit.errors)

        self.memory.save_episode_summary(
            EpisodeSummary(
                episode_num=episode_num,
                summary=plan.get("episode_summary", ""),
                mood=plan.get("mood", ""),
                cliffhanger=plan.get("cliffhanger", ""),
            )
        )
        self.memory.update_series_state(current_episode=episode_num)
        self.project.create_snapshot(episode_num)
        return result

    def build_context(self, episode_num: int) -> EpisodeContext:
        previous = self.memory.get_episode_summary(episode_num - 1)
        return EpisodeContext(
            episode_num=episode_num,
            video_path=self.project.episode_video_path(episode_num),
            asr_text=self._load_asr(episode_num),
            known_characters=[c.model_dump() for c in self.memory.get_active_characters(limit=20)],
            open_threads=[t.model_dump() for t in self.memory.get_open_threads()],
            previous_summary=previous.summary if previous else "",
            series_state=self.memory.get_series_state().model_dump(),
            project_root=self.project.root,
        )

    def generate_final_report(self, results: list[ExecutionResult]) -> dict[str, Any]:
        output_dir = self.project.root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_id": self.config.project_id,
            "drama_title": self.config.drama_title,
            "episodes_processed": len(results),
            "results": [
                {
                    "episode_num": r.episode_num,
                    "summary": r.summary,
                    "actions_total": r.actions_total,
                    "actions_succeeded": r.actions_succeeded,
                    "actions_failed": r.actions_failed,
                    "patches_committed": r.patches_committed,
                    "errors": r.errors,
                    "candidate_interactions": r.candidate_interactions,
                }
                for r in results
            ],
            "characters": self.memory.export_table("characters"),
            "relationships": self.memory.export_table("relationships"),
            "plot_events": self.memory.export_table("plot_events"),
            "plot_threads": self.memory.export_table("plot_threads"),
            "episode_summaries": self.memory.export_table("episode_summaries"),
        }
        (output_dir / "report.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "characters.json").write_text(
            json.dumps(payload["characters"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "relationships.json").write_text(
            json.dumps(payload["relationships"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "plot_events.json").write_text(
            json.dumps(payload["plot_events"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "plot_threads.json").write_text(
            json.dumps(payload["plot_threads"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (output_dir / "report.md").write_text(render_markdown_report(payload), encoding="utf-8")
        return payload

    def _determine_start_episode(self) -> int:
        if self.config.start_episode > 1:
            return self.config.start_episode
        current = self.memory.get_series_state().current_episode
        return current + 1 if current > 0 else 1

    def _load_asr(self, episode_num: int) -> str:
        asr_path = self.project.root / "asr" / f"ep{episode_num:02d}.json"
        if not asr_path.exists():
            return ""
        return format_asr_for_prompt(read_asr_file(asr_path))

    def _ensure_asr(self, episode_num: int) -> None:
        asr_path = self.project.root / "asr" / f"ep{episode_num:02d}.json"
        if asr_path.exists():
            return
        result = self.asr.transcribe(self.project.episode_video_path(episode_num))
        asr_path.parent.mkdir(parents=True, exist_ok=True)
        asr_path.write_text(json.dumps(result.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _batch_asr(self, start: int, end: int) -> None:
        if not self.asr.enabled:
            return
        for episode_num in range(start, end + 1):
            print(f"ASR ep{episode_num:02d}: start")
            self._ensure_asr(episode_num)
            print(f"ASR ep{episode_num:02d}: done")

    def _write_action_plan(self, episode_num: int, plan: dict[str, Any]) -> None:
        out = self.project.root / "action_plans" / f"ep{episode_num:02d}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
