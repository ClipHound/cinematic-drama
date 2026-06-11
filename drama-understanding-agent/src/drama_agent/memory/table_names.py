from __future__ import annotations


ALLOWED_TABLES = {
    "characters",
    "character_states",
    "relationships",
    "plot_events",
    "plot_threads",
    "episode_summaries",
    "series_state",
    "character_assets",
    "evidence_assets",
    "state_patches",
    "operation_logs",
}


def validate_table(table: str) -> None:
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table name: {table}")
