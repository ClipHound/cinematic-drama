from pathlib import Path

from drama_agent.engine.episode_loop import EpisodeLoop
from drama_agent.project import ProjectConfig


class FakeModel:
    def understand_episode(self, video_path: Path, episode_prompt: str, system_prompt: str) -> str:
        episode = "1" if "Episode: 1" in episode_prompt else "2"
        return f"""{{
          "episode_summary": "Episode {episode} summary.",
          "mood": "tense",
          "cliffhanger": "hook",
          "candidate_interactions": [
            {{
              "start_ms": 1000,
              "end_ms": 9000,
              "anchor_line": "line {episode}",
              "emotion_type": "curious",
              "intensity": 0.8,
              "reason": "viewer wants to know",
              "visual_cue": "Su Yu looks calm",
              "is_cliffhanger": false
            }}
          ],
          "actions": [
            {{
              "action": "upsert_character",
              "name": "Su Yu",
              "description": "Hidden master episode {episode}",
              "aliases": ["Su Gongzi"],
              "emotion": "calm",
              "goal": "hide identity"
            }},
            {{
              "action": "append_plot_event",
              "event_type": "reveal",
              "description": "Event {episode}",
              "characters": ["Su Yu"],
              "importance": 0.9
            }}
          ]
        }}"""


def test_episode_loop_runs_with_fake_model(tmp_path: Path) -> None:
    video_dir = tmp_path / "videos"
    video_dir.mkdir()
    (video_dir / "ep01.mp4").write_bytes(b"fake")
    (video_dir / "ep02.mp4").write_bytes(b"fake")
    config = ProjectConfig(
        project_id="demo",
        drama_title="Demo",
        video_dir=video_dir,
        video_pattern="ep{num:02d}.mp4",
        total_episodes=2,
        output_dir=tmp_path / "project",
        model_endpoint="endpoint",
        model_token="token",
        model_name="model",
    )

    result = EpisodeLoop(config, model=FakeModel()).run()

    assert result["episodes_processed"] == 2
    assert result["results"][0]["candidate_interactions"][0]["anchor_line"] == "line 1"
    assert len(result["characters"]) == 1
    assert len(result["plot_events"]) == 2
    assert (config.output_dir / "snapshots" / "after_ep02.db").exists()
    assert (config.output_dir / "output" / "report.json").exists()
    report_md = (config.output_dir / "output" / "report.md").read_text(encoding="utf-8")
    assert "## Episode Summaries" in report_md
    assert "## Characters" in report_md
    assert "## Timeline" in report_md
    assert "## Processing Results" in report_md
    assert "Episode 1 summary." in report_md
    assert "Su Yu" in report_md
