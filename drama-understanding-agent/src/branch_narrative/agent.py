from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from branch_narrative.config import BranchNarrativeConfig
from branch_narrative.context_builder import build_branch_context
from branch_narrative.image_generator import PlaceholderGenerator
from branch_narrative.output_writer import write_branch_package
from branch_narrative.phase1_planning import JsonLLM, run_planning
from branch_narrative.phase2_narrative import generate_endings, generate_nodes
from branch_narrative.phase3_visual import attach_visuals
from branch_narrative.phase4_validation import validate_package


@dataclass(slots=True)
class BranchNarrativeResult:
    package_path: Path
    total_nodes: int
    endings_count: int
    warnings: list[str]


class BranchNarrativeAgent:
    def __init__(self, llm: JsonLLM, config: BranchNarrativeConfig | None = None):
        self.llm = llm
        self.config = config or BranchNarrativeConfig()

    def run(
        self,
        *,
        project_dir: Path,
        output_dir: Path,
        drama_id: str | None = None,
        interactions_dir: Path | None = None,
    ) -> BranchNarrativeResult:
        context = build_branch_context(
            project_dir=project_dir,
            interactions_dir=interactions_dir,
            drama_id=drama_id or "",
        )
        resolved_drama_id = drama_id or context.get("drama_id") or "drama"
        plan = run_planning(self.llm, context, self.config)
        nodes = generate_nodes(self.llm, context, plan)
        endings = generate_endings(self.llm, context, plan)
        attach_visuals(
            nodes=nodes,
            endings=endings,
            context=context,
            image_generator=PlaceholderGenerator(),
        )
        warnings = validate_package(
            entry_node="n_opening",
            nodes=nodes,
            endings=endings,
            config=self.config,
        )
        package = self._package(resolved_drama_id, plan, nodes, endings, warnings)
        path = write_branch_package(package, output_dir, str(resolved_drama_id))
        return BranchNarrativeResult(
            package_path=path,
            total_nodes=len(nodes) + len(endings),
            endings_count=len(endings),
            warnings=warnings,
        )

    def _package(self, drama_id: str, plan: dict, nodes: dict, endings: dict, warnings: list[str]) -> dict:
        route_tags = [item.get("id") for item in plan.get("route_tags", []) if item.get("id")]
        return {
            "drama_id": drama_id,
            "branch_narrative_version": self.config.version,
            "generated_at": datetime.now(UTC).isoformat(),
            "metadata": {
                "total_nodes": len(nodes) + len(endings),
                "content_nodes": len(nodes),
                "total_choices": self.config.target_choice_depth,
                "endings_count": len(endings),
                "route_tags": route_tags,
                "warnings": warnings,
            },
            "entry_node": "n_opening",
            "route_tags": plan.get("route_tags", []),
            "nodes": {node_id: node.model_dump() for node_id, node in nodes.items()},
            "endings": {ending_id: ending.model_dump() for ending_id, ending in endings.items()},
        }
