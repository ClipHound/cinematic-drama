from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from interaction_designer.config import DesignConfig
from interaction_designer.context_builder import (
    build_episode_context,
    build_global_context,
    episode_numbers,
    load_project_context,
)
from interaction_designer.output_formatter import infer_duration_ms, write_episode_design
from interaction_designer.pass1_global import JsonLLM, run_global_pass
from interaction_designer.pass2_episode import run_episode_pass
from interaction_designer.safety_rules import normalize_design_output


@dataclass(slots=True)
class DesignResult:
    episode_num: int
    manifest_path: Path
    interaction_count: int
    warnings: list[str]


class InteractionDesignAgent:
    def __init__(self, llm: JsonLLM):
        self.llm = llm

    def run(
        self,
        *,
        project_dir: Path,
        output_dir: Path,
        drama_id: str | None = None,
        video_base_url: str = "",
        video_dir: Path | None = None,
        video_pattern: str = "ep{num:02d}.mp4",
        blueprint_path: Path | None = None,
        design_config: DesignConfig | None = None,
    ) -> list[DesignResult]:
        config = design_config or DesignConfig()
        ctx = load_project_context(project_dir)
        global_context = build_global_context(ctx)
        resolved_drama_id = drama_id or global_context.get("project_id") or "drama"
        if blueprint_path and blueprint_path.exists():
            blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))
        else:
            blueprint = run_global_pass(self.llm, global_context)
        blueprint_out = output_dir / str(resolved_drama_id) / "rhythm_blueprint.json"
        blueprint_out.parent.mkdir(parents=True, exist_ok=True)
        blueprint_out.write_text(json.dumps(blueprint, ensure_ascii=False, indent=2), encoding="utf-8")
        results: list[DesignResult] = []
        recent_component_sets: list[set[str]] = []
        for episode_num in episode_numbers(ctx):
            episode_context = build_episode_context(
                ctx,
                episode_num,
                blueprint,
                video_dir=video_dir,
                video_pattern=video_pattern,
                config=config,
            )
            episode_context["recent_themes"] = [sorted(items) for items in recent_component_sets[-2:]]
            design = run_episode_pass(self.llm, episode_context)
            duration_ms = infer_duration_ms(
                video_dir,
                video_pattern,
                episode_num,
                design,
                asr_data=episode_context.get("asr") or {},
            )
            design, warnings = normalize_design_output(
                design,
                episode_id=f"ep_{episode_num:03d}",
                duration_ms=duration_ms,
                config=config,
            )
            components_used = {point["component"] for point in design.get("interaction_points", [])}
            if (
                components_used
                and len(recent_component_sets) >= 2
                and components_used == recent_component_sets[-1] == recent_component_sets[-2]
            ):
                warnings.append(f"G9: 连续3集使用相同组件集合 {sorted(components_used)}")
            design["warnings"] = warnings
            recent_component_sets.append(components_used)
            path = write_episode_design(
                design=design,
                drama_id=str(resolved_drama_id),
                episode_num=episode_num,
                output_dir=output_dir,
                video_base_url=video_base_url,
                video_dir=video_dir,
                video_pattern=video_pattern,
                asr_data=episode_context.get("asr") or {},
            )
            results.append(
                DesignResult(
                    episode_num=episode_num,
                    manifest_path=path,
                    interaction_count=len(design.get("interaction_points") or []),
                    warnings=warnings,
                )
            )
        return results
