from __future__ import annotations

from django.utils import timezone

from .models import DeviceUser


def normalize_device_id(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return "anonymous"
    return "".join(char for char in raw if char.isalnum() or char in "._-")[:128] or "anonymous"


def get_device_user(request) -> DeviceUser:
    device_id = normalize_device_id(request.headers.get("X-Device-Id"))
    user, created = DeviceUser.objects.get_or_create(
        device_id=device_id,
        defaults={
            "display_name": "设备观众",
            "avatar_text": device_id[:1].upper() if device_id != "anonymous" else "A",
        },
    )
    user.last_seen_at = timezone.now()
    user.save(update_fields=["last_seen_at"])
    return user
