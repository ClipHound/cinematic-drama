from __future__ import annotations

from drama_agent.memory.schemas import Character
from drama_agent.memory.store import MemoryStore


def find_character_fuzzy(memory: MemoryStore, name: str) -> Character | None:
    if not name:
        return None
    exact = memory.find_character_by_name(name)
    if exact:
        return exact
    normalized = normalize_name(name)
    for character in memory.get_active_characters():
        for candidate in [character.name, *character.aliases]:
            candidate_normalized = normalize_name(candidate)
            if candidate_normalized and (
                candidate_normalized in normalized or normalized in candidate_normalized
            ):
                return character
    return None


def normalize_name(value: str) -> str:
    for token in ("示例王朝", "王朝", "皇帝", "陛下", "公子", "姑娘", "贴身", "近卫", "将军", "侯爷"):
        value = value.replace(token, "")
    return value.strip()


def normalize_text(value: str) -> str:
    return "".join(value.split()).lower()
