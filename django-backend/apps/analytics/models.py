from __future__ import annotations

from django.db import models


class Favorite(models.Model):
    device_user = models.ForeignKey("accounts.DeviceUser", related_name="favorites", on_delete=models.CASCADE)
    drama = models.ForeignKey("catalog.Drama", related_name="favorites", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["device_user", "drama"], name="unique_favorite_per_user_drama"),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.device_user_id}:{self.drama_id}"


class WatchProgress(models.Model):
    device_user = models.ForeignKey("accounts.DeviceUser", related_name="watch_progress", on_delete=models.CASCADE)
    drama = models.ForeignKey("catalog.Drama", related_name="watch_progress", on_delete=models.CASCADE)
    episode = models.ForeignKey("catalog.Episode", related_name="watch_progress", on_delete=models.CASCADE)
    progress_ms = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["device_user", "episode"], name="unique_watch_progress_per_user_episode"),
        ]
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.device_user_id}:{self.episode_id}:{self.progress_ms}"


class UserActivity(models.Model):
    device_user = models.ForeignKey("accounts.DeviceUser", related_name="activities", on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=80, db_index=True)
    drama = models.ForeignKey("catalog.Drama", related_name="activities", null=True, blank=True, on_delete=models.SET_NULL)
    episode = models.ForeignKey("catalog.Episode", related_name="activities", null=True, blank=True, on_delete=models.SET_NULL)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["device_user", "activity_type", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.device_user_id}:{self.activity_type}"
