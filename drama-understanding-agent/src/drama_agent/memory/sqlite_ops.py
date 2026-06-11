from __future__ import annotations

import sqlite3
from typing import Any

from drama_agent.memory.table_names import validate_table


def insert_with_conn(
    conn: sqlite3.Connection,
    table: str,
    data: dict[str, Any],
) -> None:
    validate_table(table)
    fields = list(data)
    placeholders = ", ".join("?" for _ in fields)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
        tuple(data[field] for field in fields),
    )


def insert_or_replace_with_conn(
    conn: sqlite3.Connection,
    table: str,
    data: dict[str, Any],
) -> None:
    validate_table(table)
    fields = list(data)
    placeholders = ", ".join("?" for _ in fields)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
        tuple(data[field] for field in fields),
    )


def update_with_conn(
    conn: sqlite3.Connection,
    table: str,
    record_id: str,
    data: dict[str, Any],
) -> None:
    validate_table(table)
    if not data:
        return
    assignments = ", ".join(f"{field} = ?" for field in data)
    conn.execute(
        f"UPDATE {table} SET {assignments} WHERE id = ?",
        tuple(data.values()) + (record_id,),
    )
