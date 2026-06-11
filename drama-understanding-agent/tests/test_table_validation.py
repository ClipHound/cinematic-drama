from pathlib import Path

import pytest

from drama_agent.memory.schemas import Character
from drama_agent.memory.store import MemoryStore


def test_dynamic_table_names_are_validated(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")

    with pytest.raises(ValueError, match="Invalid table name"):
        store.export_table("characters; DROP TABLE characters")


def test_invalid_patch_table_rolls_back_previous_writes(tmp_path: Path) -> None:
    from drama_agent.engine.state_patch import PatchCommitter
    from drama_agent.memory.schemas import StatePatch

    store = MemoryStore(tmp_path / "memory.db")
    good = StatePatch(
        episode_num=1,
        table="characters",
        operation="insert",
        record_id="char-ok",
        field_changes=Character(name="A", first_seen=1).model_dump(),
    )
    bad = StatePatch(
        episode_num=1,
        table="invalid_table",
        operation="insert",
        record_id="bad",
        field_changes={"id": "bad"},
    )

    result = PatchCommitter(store).commit_episode_patches([good, bad])

    assert result.patches_committed == 0
    assert "Invalid table name" in result.errors[0]
    assert store.get_active_characters() == []
