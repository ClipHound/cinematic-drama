from __future__ import annotations

from typing import Any

from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.memory.schemas import OperationLog
from drama_agent.memory.store import MemoryStore


def handle_mark_uncertain(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list:
    memory.record_operation(
        OperationLog(
            episode_num=ctx.episode_num,
            action_type="mark_uncertain",
            action_data=action,
            result=action.get("description", ""),
        )
    )
    return []
