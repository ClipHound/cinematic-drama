from pathlib import Path

from drama_agent.engine.action_plan import ActionPlanEngine
from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.engine.state_patch import PatchCommitter
from drama_agent.memory.store import MemoryStore


def test_same_character_pair_updates_existing_relationship(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    engine = ActionPlanEngine(store)
    committer = PatchCommitter(store)

    for episode, relation in [(1, "君臣"), (2, "绝对信任的君臣")]:
        plan = {
            "actions": [
                {"action": "upsert_character", "name": "君主B", "description": "皇帝"},
                {"action": "upsert_character", "name": "臣子D", "description": "护卫"},
                {
                    "action": "update_relationship",
                    "character_a": "君主B",
                    "character_b": "臣子D",
                    "relation": relation,
                },
            ]
        }
        ctx = EpisodeContext(episode_num=episode, video_path=tmp_path / f"ep{episode:02d}.mp4")
        _, patches = engine.execute(plan, ctx)
        committer.commit_episode_patches(patches)

    relationships = store.export_table("relationships")
    assert len(relationships) == 1
    assert relationships[0]["relation"] == "绝对信任的君臣"
