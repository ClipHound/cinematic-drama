from pathlib import Path

from drama_agent.engine.action_plan import ActionPlanEngine
from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.engine.state_patch import PatchCommitter
from drama_agent.memory.store import MemoryStore


def test_same_normalized_title_updates_existing_plot_thread(tmp_path: Path) -> None:
    store = MemoryStore(tmp_path / "memory.db")
    engine = ActionPlanEngine(store)
    committer = PatchCommitter(store)

    for episode, title, description in [
        (1, "主线危机", "外敌挑战国体。"),
        (2, " 主线危机 ", "君主命臣子暗中测试权贵子弟。"),
    ]:
        plan = {
            "actions": [
                {
                    "action": "update_plot_thread",
                    "title": title,
                    "description": description,
                    "thread_type": "mainplot",
                    "characters": [],
                }
            ]
        }
        ctx = EpisodeContext(episode_num=episode, video_path=tmp_path / f"ep{episode:02d}.mp4")
        _, patches = engine.execute(plan, ctx)
        committer.commit_episode_patches(patches)

    threads = store.export_table("plot_threads")
    assert len(threads) == 1
    assert threads[0]["opened_at"] == 1
    assert threads[0]["description"] == "君主命臣子暗中测试权贵子弟。"
