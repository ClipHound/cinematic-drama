from __future__ import annotations


VALID_EVENT_TYPES = {"setup", "conflict", "climax", "resolution", "reveal", "twist"}

EVENT_TYPE_ALIASES = {
    "action": "conflict",
    "command": "setup",
    "decision": "setup",
    "discovery": "reveal",
    "order": "setup",
    "plan": "setup",
    "turning_point": "twist",
}


def normalize_event_type(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in VALID_EVENT_TYPES:
        return raw
    return EVENT_TYPE_ALIASES.get(raw, "setup")
