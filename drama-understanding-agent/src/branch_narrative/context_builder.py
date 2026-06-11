from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_branch_context(
    *,
    project_dir: Path,
    interactions_dir: Path | None = None,
    drama_id: str = "",
    recent_episodes: int = 3,
) -> dict[str, Any]:
    report = json.loads((project_dir / "output" / "report.json").read_text(encoding="utf-8"))
    episode_nums = _episode_numbers(report)
    last_episode = max(episode_nums) if episode_nums else int(report.get("episodes_processed") or 0)
    assets = _character_assets(project_dir)
    return {
        "project_id": report.get("project_id", ""),
        "drama_id": drama_id or report.get("project_id", "drama"),
        "drama_title": report.get("drama_title", ""),
        "last_episode": last_episode,
        "characters": report.get("characters", [])[:20],
        "relationships": report.get("relationships", [])[:30],
        "open_threads": [
            item for item in report.get("plot_threads", []) if str(item.get("status") or "open").lower() == "open"
        ],
        "recent_summaries": _recent_summaries(report, last_episode, recent_episodes),
        "recent_events": _recent_events(report, last_episode, recent_episodes),
        "last_episode_interaction": _load_last_interaction(interactions_dir, last_episode),
        "dialogue_samples": _dialogue_samples(project_dir, last_episode),
        "character_assets": assets,
    }


def _episode_numbers(report: dict[str, Any]) -> list[int]:
    nums = {int(item.get("episode_num") or 0) for item in report.get("episode_summaries", [])}
    nums.update(int(item.get("episode_num") or 0) for item in report.get("results", []))
    return sorted(num for num in nums if num > 0)


def _recent_summaries(report: dict[str, Any], last_episode: int, recent_episodes: int) -> list[dict[str, Any]]:
    floor = max(1, last_episode - recent_episodes + 1)
    summaries = []
    for item in report.get("episode_summaries", []):
        episode_num = int(item.get("episode_num") or 0)
        if floor <= episode_num <= last_episode:
            summaries.append(item)
    return sorted(summaries, key=lambda item: item.get("episode_num", 0))


def _recent_events(report: dict[str, Any], last_episode: int, recent_episodes: int) -> list[dict[str, Any]]:
    floor = max(1, last_episode - recent_episodes + 1)
    return [
        item
        for item in report.get("plot_events", [])
        if floor <= int(item.get("episode_num") or 0) <= last_episode
    ][-20:]


def _load_last_interaction(interactions_dir: Path | None, last_episode: int) -> dict[str, Any]:
    if interactions_dir is None:
        return {}
    path = interactions_dir / f"ep_{last_episode:03d}.interactions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "episode_id": data.get("episode_id", ""),
        "episode_end_interaction": data.get("episode_end_interaction", {}),
        "design_notes": data.get("design_notes", ""),
    }


def _dialogue_samples(project_dir: Path, last_episode: int) -> list[str]:
    samples: list[str] = []
    for episode_num in range(max(1, last_episode - 1), last_episode + 1):
        path = project_dir / "asr" / f"ep{episode_num:02d}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sentences = data.get("sentences") or []
        samples.extend(str(item.get("text") or "") for item in sentences[:8])
    return [item for item in samples if item][:20]


def _character_assets(project_dir: Path) -> dict[str, list[str]]:
    asset_dir = project_dir / "assets" / "characters"
    if not asset_dir.exists():
        return {}
    assets: dict[str, list[str]] = {}
    for path in asset_dir.glob("*"):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        name = path.stem.split("_")[-1]
        assets.setdefault(name, []).append(str(path))
    return assets
