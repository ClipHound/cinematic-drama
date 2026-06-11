from __future__ import annotations

from typing import Any

from drama_agent.engine.episode_types import EpisodeContext
from drama_agent.memory.schemas import (
    Character,
    CharacterState,
    PlotEvent,
    PlotThread,
    Relationship,
    StatePatch,
    utc_now,
)
from drama_agent.memory.store import MemoryStore
from drama_agent.tools.normalizers import normalize_event_type
from drama_agent.tools.utils import find_character_fuzzy, normalize_text


def handle_upsert_character(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    match_name = action.get("match_existing")
    if not isinstance(match_name, str):
        match_name = None
    confidence = float(action.get("match_confidence") or 0.95)
    name = action.get("name") or match_name or "unknown"
    aliases = list(action.get("aliases") or [])
    mapped_id = _mapped_character_id(ctx, [name, match_name, *aliases])
    existing = memory.get_character(mapped_id) if mapped_id else find_character_fuzzy(memory, match_name or name)
    description = action.get("description", "")

    if existing:
        record_id = existing.id
        character_data = existing.model_dump()
        character_data.update(
            {
                "name": existing.name,
                "aliases": sorted(set(existing.aliases + aliases + [name])),
                "description": description or existing.description,
                "last_seen": ctx.episode_num,
                "confidence": confidence,
                "updated_at": utc_now(),
            }
        )
        operation = "update"
    else:
        character = Character(
            id=mapped_id or Character.model_fields["id"].default_factory(),
            name=name,
            aliases=aliases,
            description=description,
            first_seen=ctx.episode_num,
            last_seen=ctx.episode_num,
            confidence=confidence,
        )
        record_id = character.id
        character_data = character.model_dump()
        operation = "insert"

    for key in [name, match_name, *aliases]:
        if key:
            ctx.character_name_map[key] = record_id

    state = CharacterState(
        character_id=record_id,
        episode_num=ctx.episode_num,
        emotion=action.get("emotion", ""),
        goal=action.get("goal", ""),
        identity=action.get("identity_change", ""),
        appearance=action.get("appearance", ""),
    )
    return [
        StatePatch(
            episode_num=ctx.episode_num,
            table="characters",
            operation=operation,
            record_id=record_id,
            field_changes=character_data if operation == "insert" else _changed_character_fields(character_data),
            confidence=confidence,
            reason=f"Character observed in episode {ctx.episode_num}",
            source_action="upsert_character",
        ),
        StatePatch(
            episode_num=ctx.episode_num,
            table="character_states",
            operation="insert",
            record_id=state.id,
            field_changes=state.model_dump(),
            confidence=0.9,
            reason=f"Episode {ctx.episode_num} character state",
            source_action="upsert_character",
        ),
    ]


def handle_update_relationship(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    char_a, patches_a = _resolve_character(memory, action.get("character_a", ""), ctx)
    char_b, patches_b = _resolve_character(memory, action.get("character_b", ""), ctx)
    key = _relationship_key(char_a, char_b, action.get("direction") or "bidirectional")
    if key in ctx.relationship_key_map:
        return patches_a + patches_b
    existing = _find_relationship(memory, char_a, char_b, action.get("direction") or "bidirectional")
    record_id = existing.id if existing else None
    relationship = Relationship(
        id=record_id or Relationship.model_fields["id"].default_factory(),
        character_a=char_a,
        character_b=char_b,
        relation=action.get("relation", ""),
        direction=action.get("direction") or "bidirectional",
        established=ctx.episode_num,
        confidence=0.85,
    )
    ctx.relationship_key_map[key] = relationship.id
    operation = "update" if existing else "insert"
    field_changes = relationship.model_dump()
    if existing:
        field_changes = {
            "relation": relationship.relation,
            "direction": relationship.direction,
            "confidence": relationship.confidence,
            "updated_at": utc_now(),
        }
    return patches_a + patches_b + [
        StatePatch(
            episode_num=ctx.episode_num,
            table="relationships",
            operation=operation,
            record_id=relationship.id,
            field_changes=field_changes,
            confidence=relationship.confidence,
            reason="Relationship update from model action",
            source_action="update_relationship",
        )
    ]


def handle_append_plot_event(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    character_ids: list[str] = []
    prereq_patches: list[StatePatch] = []
    for name in action.get("characters", []):
        character_id, patches = _resolve_character(memory, name, ctx)
        character_ids.append(character_id)
        prereq_patches.extend(patches)
    event = PlotEvent(
        episode_num=ctx.episode_num,
        start_time=action.get("start_time", ""),
        end_time=action.get("end_time", ""),
        event_type=normalize_event_type(action.get("event_type")),
        description=action.get("description", ""),
        characters=character_ids,
        importance=float(action.get("importance") or 0.5),
    )
    return prereq_patches + [
        StatePatch(
            episode_num=ctx.episode_num,
            table="plot_events",
            operation="insert",
            record_id=event.id,
            field_changes=event.model_dump(),
            confidence=0.9,
            reason="Plot event observed in current episode",
            source_action="append_plot_event",
        )
    ]


def handle_update_plot_thread(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    title = action.get("title", "")
    normalized_title = normalize_text(title)
    if normalized_title in ctx.thread_title_map:
        return []
    existing = _find_plot_thread(memory, title)
    character_ids: list[str] = []
    prereq_patches: list[StatePatch] = []
    for name in action.get("characters", []):
        character_id, patches = _resolve_character(memory, name, ctx)
        character_ids.append(character_id)
        prereq_patches.extend(patches)
    confidence = 0.9
    if action.get("status") == "resolved" and not action.get("resolution"):
        confidence = 0.7
    thread = PlotThread(
        id=existing["id"] if existing else PlotThread.model_fields["id"].default_factory(),
        title=action.get("title", ""),
        description=action.get("description", ""),
        thread_type=action.get("thread_type") or "foreshadow",
        status=action.get("status") or "open",
        opened_at=existing["opened_at"] if existing else ctx.episode_num,
        resolved_at=ctx.episode_num if action.get("status") == "resolved" else None,
        resolution=action.get("resolution", ""),
        characters=character_ids,
        confidence=confidence,
    )
    ctx.thread_title_map[normalized_title] = thread.id
    operation = "update" if existing else "insert"
    field_changes = thread.model_dump()
    if existing:
        field_changes = {
            "description": thread.description,
            "thread_type": thread.thread_type,
            "status": thread.status,
            "resolved_at": thread.resolved_at,
            "resolution": thread.resolution,
            "characters": sorted(set(existing.get("characters", []) + thread.characters)),
            "confidence": thread.confidence,
            "updated_at": utc_now(),
        }
    return prereq_patches + [
        StatePatch(
            episode_num=ctx.episode_num,
            table="plot_threads",
            operation=operation,
            record_id=thread.id,
            field_changes=field_changes,
            confidence=confidence,
            reason="Plot thread update from model action",
            source_action="update_plot_thread",
        )
    ]


def handle_update_series_state(action: dict[str, Any], ctx: EpisodeContext, memory: MemoryStore) -> list[StatePatch]:
    field = action.get("field")
    if field not in {"main_plot_summary", "genre", "setting", "tone"}:
        return []
    return [
        StatePatch(
            episode_num=ctx.episode_num,
            table="series_state",
            operation="update",
            record_id="1",
            field_changes={field: action.get("value", ""), "updated_at": utc_now()},
            confidence=0.85,
            reason=f"Series state field {field} updated",
            source_action="update_series_state",
        )
    ]


def _resolve_character(memory: MemoryStore, name: str, ctx: EpisodeContext) -> tuple[str, list[StatePatch]]:
    if name in ctx.character_name_map:
        return ctx.character_name_map[name], []
    existing = find_character_fuzzy(memory, name)
    if existing:
        ctx.character_name_map[name] = existing.id
        if existing.last_seen >= ctx.episode_num:
            return existing.id, []
        return existing.id, [
            StatePatch(
                episode_num=ctx.episode_num,
                table="characters",
                operation="update",
                record_id=existing.id,
                field_changes={"last_seen": ctx.episode_num, "updated_at": utc_now()},
                confidence=0.95,
                reason=f"Character referenced in episode {ctx.episode_num}",
                source_action="resolve_character",
            )
        ]
    character = Character(name=name or "unknown", first_seen=ctx.episode_num, last_seen=ctx.episode_num, confidence=0.6)
    ctx.character_name_map[name] = character.id
    patch = StatePatch(
        episode_num=ctx.episode_num,
        table="characters",
        operation="insert",
        record_id=character.id,
        field_changes=character.model_dump(),
        confidence=0.6,
        reason=f"Implicit character reference in episode {ctx.episode_num}",
        source_action="resolve_character",
        conflicts=["Character was inferred from a reference, not an explicit upsert_character action"],
    )
    return character.id, [patch]


def _mapped_character_id(ctx: EpisodeContext, names: list[str | None]) -> str | None:
    for name in names:
        if name and name in ctx.character_name_map:
            return ctx.character_name_map[name]
    return None


def _relationship_key(character_a: str, character_b: str, direction: str) -> str:
    if direction == "bidirectional":
        left, right = sorted([character_a, character_b])
        return f"{left}|{right}|bidirectional"
    return f"{character_a}|{character_b}|{direction}"


def _find_relationship(memory: MemoryStore, character_a: str, character_b: str, direction: str) -> Relationship | None:
    target = _relationship_key(character_a, character_b, direction)
    for relationship in memory.get_active_relationships():
        key = _relationship_key(relationship.character_a, relationship.character_b, relationship.direction)
        if key == target:
            return relationship
    return None


def _find_plot_thread(memory: MemoryStore, title: str) -> dict[str, Any] | None:
    target = normalize_text(title)
    for thread in memory.export_table("plot_threads"):
        if normalize_text(thread.get("title", "")) == target:
            return thread
    return None


def _changed_character_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data[key]
        for key in ("name", "aliases", "description", "last_seen", "confidence", "updated_at")
        if key in data
    }
