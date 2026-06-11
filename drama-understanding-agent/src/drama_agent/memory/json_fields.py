from __future__ import annotations

import json
from typing import Any


JSON_FIELDS = {
    "characters": {"aliases"},
    "plot_events": {"characters"},
    "plot_threads": {"characters"},
    "episode_summaries": {"key_events"},
    "state_patches": {"patch_data"},
    "operation_logs": {"action_data"},
}


def encode_json_fields(table: str, data: dict[str, Any]) -> dict[str, Any]:
    encoded = dict(data)
    for field in JSON_FIELDS.get(table, set()):
        if field in encoded and not isinstance(encoded[field], str):
            encoded[field] = json.dumps(encoded[field], ensure_ascii=False)
    return encoded


def decode_json_fields(table: str, data: dict[str, Any]) -> dict[str, Any]:
    decoded = dict(data)
    for field in JSON_FIELDS.get(table, set()):
        if field in decoded and isinstance(decoded[field], str):
            decoded[field] = json.loads(decoded[field] or "[]")
    return decoded
