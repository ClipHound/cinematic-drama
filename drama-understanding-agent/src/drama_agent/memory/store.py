from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel

from drama_agent.memory.schemas import (
    Character,
    CharacterAsset,
    CharacterState,
    EpisodeSummary,
    EvidenceAsset,
    OperationLog,
    PlotEvent,
    PlotThread,
    Relationship,
    SeriesState,
    StatePatch,
    utc_now,
)
from drama_agent.memory.json_fields import decode_json_fields, encode_json_fields
from drama_agent.memory.schema_sql import SCHEMA_SQL
from drama_agent.memory.sqlite_ops import insert_or_replace_with_conn, insert_with_conn, update_with_conn
from drama_agent.memory.table_names import validate_table

T = TypeVar("T", bound=BaseModel)


class MemoryStore:
    """SQLite-backed structured memory store."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute(
                """
                INSERT OR IGNORE INTO series_state (id, updated_at)
                VALUES (1, ?)
                """,
                (utc_now(),),
            )

    def upsert_character(self, character: Character) -> Character:
        data = character.model_dump()
        data["aliases"] = json.dumps(data["aliases"], ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO characters (
                    id, name, aliases, description, first_seen, last_seen, status,
                    merged_into, confidence, created_at, updated_at
                )
                VALUES (
                    :id, :name, :aliases, :description, :first_seen, :last_seen, :status,
                    :merged_into, :confidence, :created_at, :updated_at
                )
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    aliases=excluded.aliases,
                    description=excluded.description,
                    first_seen=excluded.first_seen,
                    last_seen=excluded.last_seen,
                    status=excluded.status,
                    merged_into=excluded.merged_into,
                    confidence=excluded.confidence,
                    updated_at=excluded.updated_at
                """,
                data,
            )
        return character

    def find_character_by_name(self, name: str) -> Character | None:
        rows = self._fetchall(
            "SELECT * FROM characters WHERE status != 'merged' ORDER BY updated_at DESC"
        )
        for row in rows:
            character = self._row_to_model(row, Character, "characters")
            if character.name == name or name in character.aliases:
                return character
        return None

    def get_character(self, character_id: str) -> Character | None:
        row = self._fetchone("SELECT * FROM characters WHERE id = ?", (character_id,))
        return self._row_to_model(row, Character, "characters") if row else None

    def get_active_characters(self, limit: int | None = None) -> list[Character]:
        sql = """
            SELECT * FROM characters
            WHERE status = 'active'
            ORDER BY last_seen DESC, updated_at DESC
        """
        params: tuple[Any, ...] = ()
        if limit:
            sql += " LIMIT ?"
            params = (limit,)
        return [self._row_to_model(row, Character, "characters") for row in self._fetchall(sql, params)]

    def save_character_state(self, state: CharacterState) -> CharacterState:
        self._upsert_model(
            "character_states",
            state,
            conflict="character_id, episode_num",
            update_fields=("emotion", "goal", "identity", "appearance", "notes"),
        )
        return state

    def upsert_relationship(self, relationship: Relationship) -> Relationship:
        self._upsert_model(
            "relationships",
            relationship,
            update_fields=(
                "character_a",
                "character_b",
                "relation",
                "direction",
                "established",
                "ended",
                "confidence",
                "updated_at",
            ),
        )
        return relationship

    def get_active_relationships(self) -> list[Relationship]:
        rows = self._fetchall(
            "SELECT * FROM relationships WHERE ended IS NULL ORDER BY updated_at DESC"
        )
        return [self._row_to_model(row, Relationship, "relationships") for row in rows]

    def add_plot_event(self, event: PlotEvent) -> PlotEvent:
        data = event.model_dump()
        data["characters"] = json.dumps(data["characters"], ensure_ascii=False)
        self._insert("plot_events", data)
        return event

    def upsert_plot_thread(self, thread: PlotThread) -> PlotThread:
        data = thread.model_dump()
        data["characters"] = json.dumps(data["characters"], ensure_ascii=False)
        self._insert_or_replace("plot_threads", data)
        return thread

    def get_open_threads(self) -> list[PlotThread]:
        rows = self._fetchall(
            "SELECT * FROM plot_threads WHERE status = 'open' ORDER BY opened_at, updated_at"
        )
        return [self._row_to_model(row, PlotThread, "plot_threads") for row in rows]

    def save_episode_summary(self, summary: EpisodeSummary) -> EpisodeSummary:
        data = summary.model_dump()
        data["key_events"] = json.dumps(data["key_events"], ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO episode_summaries (
                    episode_num, summary, key_events, mood, cliffhanger, created_at
                )
                VALUES (
                    :episode_num, :summary, :key_events, :mood, :cliffhanger, :created_at
                )
                ON CONFLICT(episode_num) DO UPDATE SET
                    summary=excluded.summary,
                    key_events=excluded.key_events,
                    mood=excluded.mood,
                    cliffhanger=excluded.cliffhanger,
                    created_at=excluded.created_at
                """,
                data,
            )
        return summary

    def get_episode_summary(self, episode_num: int) -> EpisodeSummary | None:
        row = self._fetchone("SELECT * FROM episode_summaries WHERE episode_num = ?", (episode_num,))
        return self._row_to_model(row, EpisodeSummary, "episode_summaries") if row else None

    def get_series_state(self) -> SeriesState:
        row = self._fetchone("SELECT * FROM series_state WHERE id = 1")
        if not row:
            return SeriesState()
        return self._row_to_model(row, SeriesState, "series_state")

    def update_series_state(self, **changes: Any) -> SeriesState:
        allowed = {"current_episode", "total_episodes", "main_plot_summary", "genre", "setting", "tone"}
        fields = {k: v for k, v in changes.items() if k in allowed}
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE series_state SET {assignments} WHERE id = 1",
                tuple(fields.values()),
            )
        return self.get_series_state()

    def add_character_asset(self, asset: CharacterAsset) -> CharacterAsset:
        self._insert("character_assets", asset.model_dump())
        return asset

    def add_evidence_asset(self, asset: EvidenceAsset) -> EvidenceAsset:
        self._insert("evidence_assets", asset.model_dump())
        return asset

    def record_patch(self, patch: StatePatch, status: str) -> None:
        data = {
            "id": patch.id,
            "episode_num": patch.episode_num,
            "patch_data": json.dumps(patch.model_dump(), ensure_ascii=False),
            "status": status,
            "confidence": patch.confidence,
            "created_at": utc_now(),
            "committed_at": utc_now() if status.startswith("committed") else None,
        }
        self._insert_or_replace("state_patches", data)

    def record_patch_with_conn(self, conn: sqlite3.Connection, patch: StatePatch, status: str) -> None:
        data = {
            "id": patch.id,
            "episode_num": patch.episode_num,
            "patch_data": json.dumps(patch.model_dump(), ensure_ascii=False),
            "status": status,
            "confidence": patch.confidence,
            "created_at": utc_now(),
            "committed_at": utc_now() if status.startswith("committed") else None,
        }
        insert_or_replace_with_conn(conn, "state_patches", data)

    def record_operation(self, log: OperationLog) -> None:
        data = log.model_dump()
        data["action_data"] = json.dumps(data["action_data"], ensure_ascii=False)
        self._insert("operation_logs", data, include_id=False)

    def apply_insert(self, table: str, data: dict[str, Any]) -> None:
        validate_table(table)
        self._insert_or_replace(table, encode_json_fields(table, data))

    def apply_update(self, table: str, record_id: str, data: dict[str, Any]) -> None:
        validate_table(table)
        encoded = encode_json_fields(table, data)
        if not encoded:
            return
        assignments = ", ".join(f"{field} = ?" for field in encoded)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                tuple(encoded.values()) + (record_id,),
            )

    def apply_delete(self, table: str, record_id: str) -> None:
        validate_table(table)
        with self.connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))

    def apply_patch_with_conn(self, conn: sqlite3.Connection, patch: StatePatch) -> None:
        validate_table(patch.table)
        if patch.operation == "insert":
            insert_or_replace_with_conn(
                conn,
                patch.table,
                encode_json_fields(patch.table, patch.field_changes),
            )
        elif patch.operation == "update":
            update_with_conn(
                conn,
                patch.table,
                patch.record_id,
                encode_json_fields(patch.table, patch.field_changes),
            )
        elif patch.operation == "delete":
            conn.execute(f"DELETE FROM {patch.table} WHERE id = ?", (patch.record_id,))

    def export_table(self, table: str) -> list[dict[str, Any]]:
        validate_table(table)
        rows = self._fetchall(f"SELECT * FROM {table}")
        return [decode_json_fields(table, dict(row)) for row in rows]

    def _insert(self, table: str, data: dict[str, Any], include_id: bool = True) -> None:
        validate_table(table)
        if not include_id:
            data = {k: v for k, v in data.items() if k != "id"}
        with self.connect() as conn:
            insert_with_conn(conn, table, data)

    def _insert_or_replace(self, table: str, data: dict[str, Any]) -> None:
        validate_table(table)
        with self.connect() as conn:
            insert_or_replace_with_conn(conn, table, data)

    def _upsert_model(
        self,
        table: str,
        model: BaseModel,
        *,
        conflict: str = "id",
        update_fields: Iterable[str],
    ) -> None:
        validate_table(table)
        data = encode_json_fields(table, model.model_dump())
        fields = list(data)
        placeholders = ", ".join(f":{field}" for field in fields)
        updates = ", ".join(f"{field}=excluded.{field}" for field in update_fields)
        with self.connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table} ({', '.join(fields)})
                VALUES ({placeholders})
                ON CONFLICT({conflict}) DO UPDATE SET {updates}
                """,
                data,
            )

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute(sql, params).fetchall())

    def _row_to_model(self, row: sqlite3.Row, model: type[T], table: str) -> T:
        data = decode_json_fields(table, dict(row))
        return model.model_validate(data)
