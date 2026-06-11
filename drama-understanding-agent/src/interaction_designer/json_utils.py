from __future__ import annotations

import json
import re
from typing import Any


def parse_json_object(text: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(text, dict):
        return text
    for candidate in _json_candidates(text.strip()):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            from json_repair import repair_json

            return json.loads(repair_json(candidate))
        except Exception:
            pass
    raise ValueError(f"Could not parse JSON object from LLM output: {text[:200]}")


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        candidates.append(fence.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    return candidates
