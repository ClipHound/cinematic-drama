from __future__ import annotations

from django.db import models
from django.utils import timezone


class DeviceUser(models.Model):
    device_id = models.CharField(max_length=128, unique=True, db_index=True)
    display_name = models.CharField(max_length=80, default="设备观众")
    avatar_text = models.CharField(max_length=8, default="D")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.device_id})"
