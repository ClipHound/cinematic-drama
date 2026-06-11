from __future__ import annotations

from django.db import models


class Comment(models.Model):
    class Status(models.TextChoices):
        VISIBLE = "visible", "Visible"
        PENDING = "pending", "Pending"
        HIDDEN = "hidden", "Hidden"
        DELETED = "deleted", "Deleted"

    device_user = models.ForeignKey("accounts.DeviceUser", related_name="comments", on_delete=models.CASCADE)
    drama = models.ForeignKey("catalog.Drama", related_name="comments", on_delete=models.CASCADE)
    episode = models.ForeignKey("catalog.Episode", related_name="comments", null=True, blank=True, on_delete=models.CASCADE)
    parent = models.ForeignKey("self", related_name="replies", null=True, blank=True, on_delete=models.CASCADE)
    content = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.VISIBLE, db_index=True)
    like_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["drama", "episode", "status", "created_at"]),
            models.Index(fields=["device_user", "created_at"]),
        ]

    def __str__(self) -> str:
        return self.content[:40]
