from pathlib import Path

from drama_agent.config import Settings
from drama_agent.project import Project, ProjectConfig


def test_project_initialize_creates_runtime_layout(tmp_path: Path) -> None:
    settings = Settings(projects_root=tmp_path / "projects", model_token="token")
    config = ProjectConfig.from_settings(
        settings,
        project_id="demo",
        drama_title="Demo",
        video_dir=tmp_path / "videos",
        video_pattern="ep{num:02d}.mp4",
        total_episodes=2,
    )

    project = Project(config)
    project.initialize()

    assert project.metadata_path.exists()
    assert (project.root / "assets" / "characters").is_dir()
    assert (project.root / "output" / "knowledge_base").is_dir()
    assert project.episode_video_path(1) == tmp_path / "videos" / "ep01.mp4"


def test_project_snapshot_round_trip(tmp_path: Path) -> None:
    config = ProjectConfig(
        project_id="demo",
        drama_title="Demo",
        video_dir=tmp_path / "videos",
        video_pattern="ep{num:02d}.mp4",
        total_episodes=1,
        output_dir=tmp_path / "project",
        model_endpoint="endpoint",
        model_token="token",
        model_name="model",
    )
    project = Project(config)
    project.initialize()

    project.db_path.write_text("v1", encoding="utf-8")
    project.create_snapshot(1)
    project.db_path.write_text("v2", encoding="utf-8")
    project.restore_snapshot(1)

    assert project.db_path.read_text(encoding="utf-8") == "v1"
