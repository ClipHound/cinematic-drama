from pathlib import Path

from drama_agent.memory.schemas import (
    Character,
    CharacterState,
    EpisodeSummary,
    PlotEvent,
    PlotThread,
    Relationship,
)
from drama_agent.memory.store import MemoryStore


def test_memory_store_character_state_and_summary(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    character = store.upsert_character(
        Character(
            name="Su Yu",
            aliases=["Su Gongzi"],
            description="Hidden master",
            first_seen=1,
            last_seen=1,
        )
    )

    store.save_character_state(
        CharacterState(
            character_id=character.id,
            episode_num=1,
            emotion="calm",
            goal="hide identity",
        )
    )
    store.save_episode_summary(
        EpisodeSummary(
            episode_num=1,
            summary="Su Yu appears.",
            key_events=["event-1"],
            mood="tense",
            cliffhanger="His power is revealed.",
        )
    )

    assert store.find_character_by_name("Su Gongzi").id == character.id
    assert store.get_active_characters()[0].aliases == ["Su Gongzi"]
    assert store.get_episode_summary(1).key_events == ["event-1"]


def test_memory_store_plot_and_relationships(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    a = store.upsert_character(Character(name="A", first_seen=1))
    b = store.upsert_character(Character(name="B", first_seen=1))

    store.upsert_relationship(
        Relationship(
            character_a=a.id,
            character_b=b.id,
            relation="rivals",
            established=1,
        )
    )
    event = store.add_plot_event(
        PlotEvent(
            episode_num=1,
            event_type="conflict",
            description="A challenges B.",
            characters=[a.id, b.id],
            importance=0.8,
        )
    )
    store.upsert_plot_thread(
        PlotThread(
            title="Hidden past",
            description="A conceals a secret.",
            opened_at=1,
            characters=[a.id],
        )
    )
    store.update_series_state(current_episode=1, total_episodes=3, genre="costume")

    assert len(store.get_active_relationships()) == 1
    assert store.export_table("plot_events")[0]["id"] == event.id
    assert store.get_open_threads()[0].characters == [a.id]
    assert store.get_series_state().genre == "costume"
