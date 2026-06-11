from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drama_agent.asr.sentence_merger import merge_to_sentences
from interaction_designer.config import DesignConfig
from interaction_designer.output_formatter import infer_duration_ms


def load_project_context(project_dir: Path) -> dict[str, Any]:
    report = json.loads((project_dir / "output" / "report.json").read_text(encoding="utf-8"))
    metadata_path = project_dir / "project.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return {"project_dir": project_dir, "report": report, "metadata": metadata}


def build_global_context(ctx: dict[str, Any]) -> dict[str, Any]:
    report = ctx["report"]
    return {
        "drama_title": report.get("drama_title") or ctx["metadata"].get("drama_title", ""),
        "project_id": report.get("project_id") or ctx["metadata"].get("project_id", ""),
        "episode_summaries": [
            {
                "episode_num": item.get("episode_num"),
                "summary": item.get("summary", ""),
                "mood": item.get("mood", ""),
                "cliffhanger": item.get("cliffhanger", ""),
            }
            for item in sorted(report.get("episode_summaries", []), key=lambda row: row.get("episode_num", 0))
        ],
        "characters": report.get("characters", [])[:12],
        "plot_threads": report.get("plot_threads", []),
        "relationships": report.get("relationships", [])[:20],
    }


def build_episode_context(
    ctx: dict[str, Any],
    episode_num: int,
    blueprint: dict[str, Any],
    *,
    video_dir: Path | None = None,
    video_pattern: str = "ep{num:02d}.mp4",
    config: DesignConfig | None = None,
) -> dict[str, Any]:
    report = ctx["report"]
    project_dir: Path = ctx["project_dir"]
    design_config = config or DesignConfig()
    candidates = _candidate_interactions(report, project_dir, episode_num)
    asr_data = _load_asr(project_dir / "asr" / f"ep{episode_num:02d}.json")
    duration_ms = infer_duration_ms(
        video_dir,
        video_pattern,
        episode_num,
        {"interaction_points": candidates},
        asr_data=asr_data,
    )
    return {
        "episode_num": episode_num,
        "summary": _episode_summary(report, episode_num),
        "plot_events": [
            event for event in report.get("plot_events", []) if int(event.get("episode_num") or 0) == episode_num
        ],
        "candidate_interactions": candidates,
        "asr": _compact_asr(asr_data),
        "duration_ms": duration_ms,
        "density_instruction": _density_instruction(duration_ms, design_config),
        "blueprint": _blueprint_for_episode(blueprint, episode_num),
        "open_threads": [
            thread for thread in report.get("plot_threads", []) if (thread.get("opened_at") or 0) <= episode_num
        ],
    }


def episode_numbers(ctx: dict[str, Any]) -> list[int]:
    report = ctx["report"]
    nums = {int(item.get("episode_num") or 0) for item in report.get("episode_summaries", [])}
    nums.update(int(event.get("episode_num") or 0) for event in report.get("plot_events", []))
    return sorted(num for num in nums if num > 0)


def _candidate_interactions(report: dict[str, Any], project_dir: Path, episode_num: int) -> list[dict[str, Any]]:
    for result in report.get("results", []):
        if int(result.get("episode_num") or 0) == episode_num:
            candidates = result.get("candidate_interactions") or []
            if candidates:
                return list(candidates)
    plan_path = project_dir / "action_plans" / f"ep{episode_num:02d}.json"
    if plan_path.exists():
        return list(json.loads(plan_path.read_text(encoding="utf-8")).get("candidate_interactions") or [])
    return []


def _episode_summary(report: dict[str, Any], episode_num: int) -> dict[str, Any]:
    for item in report.get("episode_summaries", []):
        if int(item.get("episode_num") or 0) == episode_num:
            return item
    for item in report.get("results", []):
        if int(item.get("episode_num") or 0) == episode_num:
            return {"episode_num": episode_num, "summary": item.get("summary", "")}
    return {"episode_num": episode_num}


def _load_asr(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _compact_asr(data: dict[str, Any]) -> dict[str, Any]:
    if not data:
        return {}
    sentences = data.get("sentences") or merge_to_sentences(
        data.get("segments") or [],
        data.get("vad_segments") or [],
    )
    return {
        "asr_available": data.get("asr_available", True),
        "text": data.get("text", ""),
        "sentences": sentences,
        "vad_end_ms": max((int(item.get("end_ms") or 0) for item in data.get("vad_segments") or []), default=0),
        "emotion_segments": data.get("emotion_segments") or [],
        "audio_events": data.get("audio_events") or [],
    }


def _blueprint_for_episode(blueprint: dict[str, Any], episode_num: int) -> dict[str, Any]:
    for item in blueprint.get("rhythm_blueprint", []):
        if int(item.get("episode_num") or 0) == episode_num:
            return item
    return {}


def _density_instruction(duration_ms: int, config: DesignConfig) -> str:
    max_points = config.max_points_for_duration(duration_ms)
    max_seconds = config.max_total_interaction_ms(duration_ms) // 1000
    duration_seconds = duration_ms // 1000 if duration_ms > 0 else "unknown"
    return (
        f"本集时长: {duration_seconds} 秒\n"
        f"互动点数量目标: {config.min_points_per_episode}-{max_points} 个\n"
        f"互动点上限: {max_points} 个\n"
        f"互动总时长上限: {max_seconds} 秒\n"
        f"相邻互动间隔: 至少 {config.min_gap_ms // 1000} 秒"
    )
