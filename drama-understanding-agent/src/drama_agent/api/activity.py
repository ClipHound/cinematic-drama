from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any


def normalize_device_id(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "anonymous"
    return "".join(char for char in raw if char.isalnum() or char in "._-")[:128] or "anonymous"


@dataclass
class ActivityStore:
    path: Path

    def __post_init__(self) -> None:
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add_events(self, device_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        device_id = normalize_device_id(device_id)
        now = datetime.now(UTC).isoformat()
        with self._lock:
            data = self._read()
            known = {str(item.get("id")) for item in data["events"] if item.get("id")}
            inserted = 0
            for event in events:
                event_id = str(event.get("id") or "")
                if not event_id or event_id in known:
                    continue
                record = {
                    "id": event_id,
                    "deviceId": device_id,
                    "dramaId": str(event.get("dramaId") or ""),
                    "episodeNumber": int(event.get("episodeNumber") or 0),
                    "pointId": str(event.get("pointId") or ""),
                    "type": str(event.get("type") or ""),
                    "actionData": event.get("actionData") if isinstance(event.get("actionData"), dict) else {},
                    "atMs": float(event.get("atMs") or 0),
                    "createdAt": str(event.get("createdAt") or now),
                    "receivedAt": now,
                }
                data["events"].append(record)
                known.add(event_id)
                inserted += 1
            self._write(data)
        return {"accepted": inserted, "duplicates": len(events) - inserted}

    def profile(self, device_id: str) -> dict[str, Any]:
        device_id = normalize_device_id(device_id)
        data = self._read()
        events = [event for event in data["events"] if event.get("deviceId") == device_id]
        watched = {
            (str(event.get("dramaId") or ""), int(event.get("episodeNumber") or 0))
            for event in events
            if event.get("dramaId") and int(event.get("episodeNumber") or 0) > 0
        }
        favorites = {
            str(event.get("dramaId") or "")
            for event in events
            if event.get("type") == "like" and event.get("dramaId")
        }
        latest = next((event for event in reversed(events) if event.get("dramaId") and event.get("episodeNumber")), None)
        return {
            "deviceId": device_id,
            "displayName": "设备观众",
            "bio": "基于本机设备 ID 的互动档案",
            "avatarText": device_id[:1].upper() if device_id != "anonymous" else "A",
            "stats": {
                "watchedEpisodes": len(watched),
                "interactions": len(events),
                "favorites": len(favorites),
            },
            "continueWatching": _continue_item(latest),
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"events": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"events": []}
        events = payload.get("events") if isinstance(payload, dict) else []
        return {"events": events if isinstance(events, list) else []}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _continue_item(event: dict[str, Any] | None) -> dict[str, Any] | None:
    if not event:
        return None
    drama_id = str(event.get("dramaId") or "")
    episode = int(event.get("episodeNumber") or 0)
    if not drama_id or episode <= 0:
        return None
    return {
        "dramaId": drama_id,
        "episodeNumber": episode,
        "title": f"{drama_id} 第 {episode} 集",
    }
