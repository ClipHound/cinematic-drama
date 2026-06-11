from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from branch_narrative.agent import BranchNarrativeAgent
from branch_narrative.config import BranchNarrativeConfig
from drama_agent.config import load_settings
from drama_agent.engine.episode_loop import EpisodeLoop
from drama_agent.memory.store import MemoryStore
from drama_agent.project import ProjectConfig
from interaction_designer.agent import InteractionDesignAgent
from interaction_designer.config import DesignConfig
from interaction_designer.llm import TextLLM


app = typer.Typer(help="Drama Understanding Agent")
console = Console()


@app.command()
def run(
    title: str = typer.Option(..., "--title"),
    video_dir: Path = typer.Option(..., "--video-dir"),
    pattern: str = typer.Option("ep{num:02d}.mp4", "--pattern"),
    episodes: int = typer.Option(..., "--episodes"),
    project_id: str | None = typer.Option(None, "--project-id"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    from_episode: int = typer.Option(1, "--from-episode"),
) -> None:
    settings = load_settings()
    pid = project_id or _slug(title)
    config = ProjectConfig.from_settings(
        settings,
        project_id=pid,
        drama_title=title,
        video_dir=video_dir,
        video_pattern=pattern,
        total_episodes=episodes,
        output_dir=output_dir,
        start_episode=from_episode,
    )
    result = EpisodeLoop(config).run()
    console.print(f"Processed {result['episodes_processed']} episode(s).")
    console.print(f"Report: {config.output_dir / 'output' / 'report.md'}")


@app.command()
def full_pipeline(
    title: str = typer.Option(..., "--title"),
    video_dir: Path = typer.Option(..., "--video-dir"),
    pattern: str = typer.Option("ep{num:02d}.mp4", "--pattern"),
    episodes: int = typer.Option(..., "--episodes"),
    project_id: str | None = typer.Option(None, "--project-id"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    interactions_output: Path = typer.Option(Path("outputs"), "--interactions-output"),
    video_base_url: str = typer.Option("", "--video-base-url"),
) -> None:
    settings = load_settings()
    pid = project_id or _slug(title)
    config = ProjectConfig.from_settings(
        settings,
        project_id=pid,
        drama_title=title,
        video_dir=video_dir,
        video_pattern=pattern,
        total_episodes=episodes,
        output_dir=output_dir,
    )
    understanding = EpisodeLoop(config).run()
    console.print(f"Processed {understanding['episodes_processed']} episode(s).")
    design_interactions(
        config.output_dir,
        interactions_output,
        pid,
        video_base_url,
        video_dir,
        pattern,
        None,
        None,
    )


@app.command()
def status(project: Path = typer.Option(..., "--project")) -> None:
    store = MemoryStore(project / "memory.db")
    state = store.get_series_state()
    console.print(
        {
            "current_episode": state.current_episode,
            "total_episodes": state.total_episodes,
            "characters": len(store.export_table("characters")),
            "events": len(store.export_table("plot_events")),
        }
    )


@app.command()
def export(project: Path = typer.Option(..., "--project")) -> None:
    store = MemoryStore(project / "memory.db")
    output_dir = project / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    for table in ("characters", "relationships", "plot_events", "plot_threads"):
        (output_dir / f"{table}.json").write_text(
            __import__("json").dumps(store.export_table(table), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    console.print(f"Exported to {output_dir}")


@app.command()
def design_interactions(
    project: Path = typer.Option(..., "--project"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir"),
    drama_id: str | None = typer.Option(None, "--drama-id"),
    video_base_url: str = typer.Option("", "--video-base-url"),
    video_dir: Path | None = typer.Option(None, "--video-dir"),
    pattern: str = typer.Option("ep{num:02d}.mp4", "--pattern"),
    blueprint: Path | None = typer.Option(None, "--blueprint"),
    design_config: Path | None = typer.Option(None, "--config"),
) -> None:
    settings = load_settings()
    llm = TextLLM(
        settings.model_endpoint,
        settings.model_token,
        settings.model_name,
        timeout=settings.request_timeout_sec,
    )
    results = InteractionDesignAgent(llm).run(
        project_dir=project,
        output_dir=output_dir,
        drama_id=drama_id,
        video_base_url=video_base_url,
        video_dir=video_dir,
        video_pattern=pattern,
        blueprint_path=blueprint,
        design_config=DesignConfig.from_file(design_config),
    )
    for result in results:
        console.print(
            f"Ep{result.episode_num:02d}: {result.interaction_count} interaction(s) -> "
            f"{result.manifest_path}"
        )


@app.command()
def branch_narrative(
    project: Path = typer.Option(..., "--project"),
    output_dir: Path = typer.Option(Path("outputs"), "--output-dir"),
    drama_id: str | None = typer.Option(None, "--drama-id"),
    interactions_dir: Path | None = typer.Option(None, "--interactions-dir"),
    image_mode: str = typer.Option("placeholder", "--image-mode"),
) -> None:
    settings = load_settings()
    llm = TextLLM(
        settings.model_endpoint,
        settings.model_token,
        settings.model_name,
        timeout=settings.request_timeout_sec,
    )
    result = BranchNarrativeAgent(
        llm,
        BranchNarrativeConfig(image_mode=image_mode),
    ).run(
        project_dir=project,
        output_dir=output_dir,
        drama_id=drama_id,
        interactions_dir=interactions_dir,
    )
    console.print(
        f"Branch narrative: {result.total_nodes} node(s), {result.endings_count} ending(s) -> "
        f"{result.package_path}"
    )
    if result.warnings:
        console.print({"warnings": result.warnings})


def _slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    return slug or "drama"


if __name__ == "__main__":
    app()
