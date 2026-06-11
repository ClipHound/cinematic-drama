from pathlib import Path

from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.memory.schemas import Character
from drama_agent.memory.store import MemoryStore
from drama_agent.tools.memory_tools import (
    handle_append_plot_event,
    handle_update_plot_thread,
    handle_update_relationship,
    handle_upsert_character,
)


def test_upsert_character_handles_boolean_match_existing(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    existing = store.upsert_character(
        Character(
            name="黑衣护卫",
            aliases=[],
            description="皇帝近卫",
            first_seen=1,
            last_seen=1,
        )
    )
    ctx = EpisodeContext(episode_num=2, video_path=tmp_path / "ep02.mp4")

    patches = handle_upsert_character(
        {
            "name": "黑衣护卫",
            "match_existing": True,
            "match_confidence": 0.95,
            "description": "皇帝贴身近卫",
        },
        ctx,
        store,
    )

    assert patches[0].operation == "update"
    assert patches[0].record_id == existing.id


def test_implicit_character_resolution_returns_patch_without_writing(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    ctx = EpisodeContext(episode_num=1, video_path=tmp_path / "ep01.mp4")

    patches = handle_append_plot_event(
        {
            "event_type": "setup",
            "description": "Unknown appears",
            "characters": ["未知角色"],
        },
        ctx,
        store,
    )

    assert any(p.table == "characters" and p.source_action == "resolve_character" for p in patches)
    assert store.get_active_characters() == []


def test_plot_event_normalizes_invalid_event_type(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    ctx = EpisodeContext(episode_num=1, video_path=tmp_path / "ep01.mp4")

    patches = handle_append_plot_event(
        {
            "event_type": "order",
            "description": "The emperor gives an order.",
            "characters": [],
        },
        ctx,
        store,
    )

    assert patches[-1].field_changes["event_type"] == "setup"


def test_relationship_handler_updates_existing_relationship(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    a = store.upsert_character(Character(name="A", first_seen=1))
    b = store.upsert_character(Character(name="B", first_seen=1))
    ctx1 = EpisodeContext(episode_num=1, video_path=tmp_path / "ep01.mp4")
    first_patches = handle_update_relationship(
        {"character_a": "A", "character_b": "B", "relation": "friends"},
        ctx1,
        store,
    )
    first = next(p for p in first_patches if p.table == "relationships")
    store.apply_insert(first.table, first.field_changes)

    ctx2 = EpisodeContext(episode_num=2, video_path=tmp_path / "ep02.mp4")
    second = handle_update_relationship(
        {"character_a": "B", "character_b": "A", "relation": "trusted allies"},
        ctx2,
        store,
    )
    relationship_patch = next(p for p in second if p.table == "relationships")

    assert relationship_patch.operation == "update"
    assert relationship_patch.record_id == first.record_id
    assert {a.id, b.id} == {first.field_changes["character_a"], first.field_changes["character_b"]}


def test_plot_thread_handler_updates_existing_title(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    store.upsert_character(Character(name="A", first_seen=1))
    ctx1 = EpisodeContext(episode_num=1, video_path=tmp_path / "ep01.mp4")
    first_patches = handle_update_plot_thread(
        {
            "title": "主线危机",
            "description": "old",
            "thread_type": "mainplot",
            "characters": ["A"],
        },
        ctx1,
        store,
    )
    first = next(p for p in first_patches if p.table == "plot_threads")
    store.apply_insert(first.table, first.field_changes)

    ctx2 = EpisodeContext(episode_num=2, video_path=tmp_path / "ep02.mp4")
    second_patches = handle_update_plot_thread(
        {
            "title": " 主线危机 ",
            "description": "new",
            "thread_type": "mainplot",
            "characters": ["A"],
        },
        ctx2,
        store,
    )
    second = next(p for p in second_patches if p.table == "plot_threads")

    assert second.operation == "update"
    assert second.record_id == first.record_id


def test_upsert_character_matches_contained_alias(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    existing = store.upsert_character(
        Character(
            name="君主B",
            aliases=["示例王朝皇帝"],
            description="示例王朝皇帝",
            first_seen=1,
            last_seen=1,
        )
    )
    ctx = EpisodeContext(episode_num=2, video_path=tmp_path / "ep02.mp4")

    patches = handle_upsert_character(
        {
            "name": "示例王朝皇帝君主B",
            "description": "示例王朝王朝皇帝",
        },
        ctx,
        store,
    )

    assert patches[0].operation == "update"
    assert patches[0].record_id == existing.id


def test_existing_character_reference_updates_last_seen(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    existing = store.upsert_character(Character(name="君主B", first_seen=1, last_seen=1))
    ctx = EpisodeContext(episode_num=2, video_path=tmp_path / "ep02.mp4")

    patches = handle_append_plot_event(
        {
            "event_type": "reveal",
            "description": "皇帝下密旨。",
            "characters": ["君主B"],
        },
        ctx,
        store,
    )

    last_seen_patch = next(p for p in patches if p.table == "characters")
    assert last_seen_patch.operation == "update"
    assert last_seen_patch.record_id == existing.id
    assert last_seen_patch.field_changes["last_seen"] == 2
