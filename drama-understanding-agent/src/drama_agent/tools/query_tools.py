from __future__ import annotations

from drama_agent.memory.store import MemoryStore


def get_character_card(memory: MemoryStore, name: str) -> dict | None:
    character = memory.find_character_by_name(name)
    return character.model_dump() if character else None


def search_events(memory: MemoryStore, limit: int = 20) -> list[dict]:
    return memory.export_table("plot_events")[:limit]
