from pathlib import Path

from drama_agent.engine.action_plan import ActionPlanEngine
from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.engine.state_patch import PatchCommitter
from drama_agent.memory.schemas import Character, StatePatch
from drama_agent.memory.store import MemoryStore


def test_action_engine_generates_and_commits_patches(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    engine = ActionPlanEngine(store)
    ctx = EpisodeContext(episode_num=1, video_path=tmp_path / "ep01.mp4")
    plan = {
        "episode_summary": "Su Yu appears.",
        "actions": [
            {
                "action": "upsert_character",
                "name": "Su Yu",
                "description": "Hidden master",
                "aliases": ["Su Gongzi"],
                "emotion": "calm",
                "goal": "hide",
            },
            {
                "action": "append_plot_event",
                "event_type": "reveal",
                "description": "Su Yu defeats attackers.",
                "characters": ["Su Yu"],
                "importance": 0.95,
            },
            {
                "action": "update_series_state",
                "field": "genre",
                "value": "costume",
            },
        ],
    }

    result, patches = engine.execute(plan, ctx)
    commit = PatchCommitter(store, patch_log_dir=tmp_path / "patches").commit_episode_patches(patches)

    assert result.actions_succeeded == 3
    assert commit.patches_committed == 4
    assert store.find_character_by_name("Su Gongzi").name == "Su Yu"
    assert store.export_table("plot_events")[0]["description"] == "Su Yu defeats attackers."
    assert store.get_series_state().genre == "costume"
    assert (tmp_path / "patches" / "ep01.json").exists()


def test_patch_commit_rolls_back_whole_episode_on_failure(tmp_path: Path) -> None:
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
        table="missing_table",
        operation="insert",
        record_id="bad",
        field_changes={"id": "bad"},
    )

    result = PatchCommitter(store).commit_episode_patches([good, bad])

    assert result.patches_committed == 0
    assert result.errors
    assert store.get_active_characters() == []


class RecordingVectors:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.synced = []
        self.deleted = []

    def sync_character(self, character):
        if self.fail:
            raise RuntimeError("sync failed")
        self.synced.append(character.id)

    def delete_point(self, collection: str, point_id: str):
        self.deleted.append((collection, point_id))


def test_patch_commit_syncs_character_vectors_after_commit(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    vectors = RecordingVectors()
    character = Character(id="char-sync", name="A", first_seen=1)
    patch = StatePatch(
        episode_num=1,
        table="characters",
        operation="insert",
        record_id=character.id,
        field_changes=character.model_dump(),
    )

    result = PatchCommitter(store, vectors=vectors).commit_episode_patches([patch])

    assert result.errors == []
    assert vectors.synced == ["char-sync"]
    assert store.get_character("char-sync") is not None


def test_vector_sync_failure_does_not_rollback_sqlite(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    vectors = RecordingVectors(fail=True)
    character = Character(id="char-sync", name="A", first_seen=1)
    patch = StatePatch(
        episode_num=1,
        table="characters",
        operation="insert",
        record_id=character.id,
        field_changes=character.model_dump(),
    )

    result = PatchCommitter(store, vectors=vectors).commit_episode_patches([patch])

    assert result.patches_committed == 1
    assert "vector sync failed" in result.errors[0]
    assert store.get_character("char-sync") is not None
