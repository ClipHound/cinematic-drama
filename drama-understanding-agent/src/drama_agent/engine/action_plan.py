from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from drama_agent.engine.episode_types import EpisodeContext, ExecutionResult
from drama_agent.memory.schemas import OperationLog, StatePatch
from drama_agent.memory.store import MemoryStore
from drama_agent.tools.asset_tools import handle_capture_frame
from drama_agent.tools.memory_tools import (
    handle_append_plot_event,
    handle_update_plot_thread,
    handle_update_relationship,
    handle_update_series_state,
    handle_upsert_character,
)
from drama_agent.tools.validation_tools import handle_mark_uncertain


Handler = Callable[[dict[str, Any], EpisodeContext, MemoryStore], list[StatePatch]]

ACTION_HANDLERS: dict[str, Handler] = {
    "upsert_character": handle_upsert_character,
    "update_relationship": handle_update_relationship,
    "append_plot_event": handle_append_plot_event,
    "update_plot_thread": handle_update_plot_thread,
    "capture_frame": handle_capture_frame,
    "update_series_state": handle_update_series_state,
    "mark_uncertain": handle_mark_uncertain,
}


def parse_action_plan(raw_text: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_text, dict):
        return raw_text
    text = raw_text.strip()
    for candidate in _json_candidates(text):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            from json_repair import repair_json

            return json.loads(repair_json(candidate))
        except Exception:
            pass
    return {"_error": "parse_failed", "raw": raw_text}


class ActionPlanEngine:
    def __init__(self, memory: MemoryStore):
        self.memory = memory

    def execute(self, plan: dict[str, Any], ctx: EpisodeContext) -> tuple[ExecutionResult, list[StatePatch]]:
        started = time.perf_counter()
        actions = plan.get("actions") or []
        result = ExecutionResult(
            episode_num=ctx.episode_num,
            summary=plan.get("episode_summary", ""),
            actions_total=len(actions),
            candidate_interactions=list(plan.get("candidate_interactions") or []),
        )
        patches: list[StatePatch] = []

        for action in actions:
            action_type = action.get("action")
            handler = ACTION_HANDLERS.get(action_type)
            if not handler:
                result.actions_failed += 1
                result.errors.append(f"Unknown action: {action_type}")
                continue
            try:
                action_patches = handler(action, ctx, self.memory)
                patches.extend(action_patches)
                result.actions_succeeded += 1
                if action_type == "mark_uncertain":
                    result.uncertainties.append(action)
                self.memory.record_operation(
                    OperationLog(
                        episode_num=ctx.episode_num,
                        action_type=action_type,
                        action_data=action,
                        result=f"patches={len(action_patches)}",
                    )
                )
            except Exception as exc:
                result.actions_failed += 1
                result.errors.append(f"{action_type}: {exc}")

        result.patches_generated = len(patches)
        result.duration_sec = time.perf_counter() - started
        return result, patches


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    return candidates
