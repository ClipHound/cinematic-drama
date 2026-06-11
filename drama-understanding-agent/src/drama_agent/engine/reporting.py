from __future__ import annotations

from typing import Any

from drama_agent.memory.schemas import utc_now


def render_markdown_report(payload: dict[str, Any]) -> str:
    characters = payload.get("characters", [])
    relationships = payload.get("relationships", [])
    plot_threads = payload.get("plot_threads", [])
    plot_events = payload.get("plot_events", [])
    candidate_count = sum(len(item.get("candidate_interactions") or []) for item in payload.get("results", []))
    summaries = {
        item.get("episode_num"): item for item in payload.get("episode_summaries", [])
    }
    character_names = _character_name_map(characters)

    lines = [
        f"# {payload.get('drama_title', '')} - 剧情理解报告",
        "",
        f"- Project: `{payload.get('project_id', '')}`",
        f"- Episodes processed: {payload.get('episodes_processed', 0)}",
        f"- Characters: {len(characters)}",
        f"- Relationships: {len(relationships)}",
        f"- Plot threads: {len(plot_threads)}",
        f"- Plot events: {len(plot_events)}",
        f"- Candidate interactions: {candidate_count}",
        f"- Generated: {utc_now()}",
        "",
        "## Episode Summaries",
        "",
    ]

    _append_episode_summaries(lines, payload.get("results", []), summaries)
    _append_characters(lines, characters)
    _append_relationships(lines, relationships, character_names)
    _append_plot_threads(lines, plot_threads, character_names)
    _append_timeline(lines, plot_events, character_names)
    _append_processing_results(lines, payload.get("results", []))
    return "\n".join(lines).rstrip() + "\n"


def _append_episode_summaries(
    lines: list[str],
    results: list[dict[str, Any]],
    summaries: dict[int, dict[str, Any]],
) -> None:
    if not results:
        lines.extend(["No episodes were processed.", ""])
        return
    for result in sorted(results, key=lambda item: item.get("episode_num", 0)):
        episode_num = result.get("episode_num", 0)
        summary = summaries.get(episode_num, {})
        lines.extend(
            [
                f"### Episode {episode_num}",
                "",
                _value(result.get("summary") or summary.get("summary"), "No summary."),
            ]
        )
        if summary.get("mood"):
            lines.append(f"- Mood: {summary['mood']}")
        if summary.get("cliffhanger"):
            lines.append(f"- Cliffhanger: {summary['cliffhanger']}")
        lines.append("")


def _append_characters(lines: list[str], characters: list[dict[str, Any]]) -> None:
    lines.extend(["## Characters", ""])
    if not characters:
        lines.extend(["No characters recorded.", ""])
        return
    ordered = sorted(
        characters,
        key=lambda item: (item.get("first_seen") or 9999, -(item.get("confidence") or 0)),
    )
    for character in ordered:
        aliases = ", ".join(character.get("aliases") or [])
        suffix = f" ({aliases})" if aliases else ""
        lines.extend(
            [
                f"### {character.get('name', 'Unknown')}{suffix}",
                "",
                _value(character.get("description"), "No description."),
                "",
                (
                    f"- Seen: Ep{character.get('first_seen', '?')} "
                    f"to Ep{character.get('last_seen', '?')}"
                ),
                f"- Status: {character.get('status', 'unknown')}",
                f"- Confidence: {character.get('confidence', 0):.2f}",
                "",
            ]
        )


def _append_relationships(
    lines: list[str],
    relationships: list[dict[str, Any]],
    character_names: dict[str, str],
) -> None:
    lines.extend(["## Relationships", ""])
    if not relationships:
        lines.extend(["No relationships recorded.", ""])
        return
    for rel in sorted(relationships, key=lambda item: item.get("updated_at", "")):
        left = character_names.get(rel.get("character_a", ""), rel.get("character_a", "?"))
        right = character_names.get(rel.get("character_b", ""), rel.get("character_b", "?"))
        lines.append(
            f"- **{left}** ↔ **{right}**: {_value(rel.get('relation'), 'unspecified')}"
        )
    lines.append("")


def _append_plot_threads(
    lines: list[str],
    threads: list[dict[str, Any]],
    character_names: dict[str, str],
) -> None:
    lines.extend(["## Plot Threads", ""])
    if not threads:
        lines.extend(["No plot threads recorded.", ""])
        return
    ordered = sorted(threads, key=lambda item: (item.get("opened_at") or 9999, item.get("title", "")))
    for thread in ordered:
        people = _names_from_ids(thread.get("characters") or [], character_names)
        status = thread.get("status", "open")
        lines.extend(
            [
                f"### {thread.get('title', 'Untitled')}",
                "",
                _value(thread.get("description"), "No description."),
                "",
                f"- Type: {thread.get('thread_type', 'unknown')}",
                f"- Status: {status}",
                f"- Opened: Ep{thread.get('opened_at', '?')}",
            ]
        )
        if thread.get("resolved_at"):
            lines.append(f"- Resolved: Ep{thread['resolved_at']}")
        if thread.get("resolution"):
            lines.append(f"- Resolution: {thread['resolution']}")
        if people:
            lines.append(f"- Characters: {', '.join(people)}")
        lines.append("")


def _append_timeline(
    lines: list[str],
    events: list[dict[str, Any]],
    character_names: dict[str, str],
) -> None:
    lines.extend(["## Timeline", ""])
    if not events:
        lines.extend(["No plot events recorded.", ""])
        return
    ordered = sorted(
        events,
        key=lambda item: (item.get("episode_num") or 0, item.get("start_time") or ""),
    )
    current_episode: int | None = None
    for event in ordered:
        episode_num = event.get("episode_num")
        if episode_num != current_episode:
            current_episode = episode_num
            lines.extend([f"### Episode {episode_num}", ""])
        people = _names_from_ids(event.get("characters") or [], character_names)
        when = _event_time(event)
        event_type = event.get("event_type", "event")
        text = f"- {when} **{event_type}**: {_value(event.get('description'), 'No description.')}"
        if people:
            text += f" Characters: {', '.join(people)}."
        lines.append(text)
    lines.append("")


def _append_processing_results(lines: list[str], results: list[dict[str, Any]]) -> None:
    lines.extend(["## Processing Results", ""])
    if not results:
        lines.extend(["No processing results recorded.", ""])
        return
    lines.append("| Episode | Actions | Failed | Patches | Errors |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for result in sorted(results, key=lambda item: item.get("episode_num", 0)):
        errors = "; ".join(result.get("errors") or []) or "-"
        lines.append(
            "| Ep{episode:02d} | {succeeded}/{total} | {failed} | {patches} | {errors} |".format(
                episode=result.get("episode_num", 0),
                succeeded=result.get("actions_succeeded", 0),
                total=result.get("actions_total", 0),
                failed=result.get("actions_failed", 0),
                patches=result.get("patches_committed", 0),
                errors=errors.replace("|", "\\|"),
            )
        )
    lines.append("")


def _character_name_map(characters: list[dict[str, Any]]) -> dict[str, str]:
    return {
        character.get("id", ""): character.get("name", character.get("id", ""))
        for character in characters
    }


def _names_from_ids(ids: list[str], character_names: dict[str, str]) -> list[str]:
    return [character_names.get(character_id, character_id) for character_id in ids]


def _event_time(event: dict[str, Any]) -> str:
    start = event.get("start_time") or "??:??"
    end = event.get("end_time") or ""
    return f"{start}-{end}" if end else start


def _value(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
