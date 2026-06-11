from __future__ import annotations

from django.db import models


class InteractionManifest(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"
        INVALID = "invalid", "Invalid"
        FAILED = "failed", "Failed"

    episode = models.OneToOneField("catalog.Episode", related_name="interaction_manifest", on_delete=models.CASCADE)
    version = models.CharField(max_length=40, default="1.0.0")
    schema_version = models.CharField(max_length=40, default="1.0.0")
    duration_ms = models.PositiveIntegerField(default=0)
    raw_json = models.JSONField(default=dict, blank=True)
    source_path = models.CharField(max_length=500, blank=True)
    generated_by = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["episode__drama__slug", "episode__episode_number"]

    def __str__(self) -> str:
        return f"{self.episode} manifest {self.version}"


class InteractionPoint(models.Model):
    manifest = models.ForeignKey(InteractionManifest, related_name="points", on_delete=models.CASCADE)
    point_key = models.CharField(max_length=120)
    component = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=160)
    emotion = models.CharField(max_length=80, blank=True)
    start_ms = models.PositiveIntegerField()
    end_ms = models.PositiveIntegerField()
    priority = models.FloatField(default=0.0)
    highlight_reason = models.TextField(blank=True)
    config = models.JSONField(default=dict, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["manifest", "sort_order", "start_ms"]
        constraints = [
            models.UniqueConstraint(fields=["manifest", "point_key"], name="unique_point_key_per_manifest"),
        ]
        indexes = [
            models.Index(fields=["component", "start_ms"]),
        ]

    def __str__(self) -> str:
        return f"{self.point_key} ({self.component})"


class InteractionEvent(models.Model):
    event_id = models.CharField(max_length=160, unique=True)
    device_user = models.ForeignKey("accounts.DeviceUser", related_name="interaction_events", on_delete=models.CASCADE)
    drama = models.ForeignKey("catalog.Drama", related_name="interaction_events", on_delete=models.CASCADE)
    episode = models.ForeignKey("catalog.Episode", related_name="interaction_events", on_delete=models.CASCADE)
    interaction_point = models.ForeignKey(
        InteractionPoint,
        related_name="events",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    event_type = models.CharField(max_length=80, db_index=True)
    action_data = models.JSONField(default=dict, blank=True)
    at_ms = models.FloatField(default=0)
    client_timestamp = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        indexes = [
            models.Index(fields=["device_user", "received_at"]),
            models.Index(fields=["drama", "episode", "received_at"]),
            models.Index(fields=["interaction_point", "event_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}:{self.event_id}"


class InteractionAggregate(models.Model):
    interaction_point = models.ForeignKey(InteractionPoint, related_name="aggregates", on_delete=models.CASCADE)
    event_type = models.CharField(max_length=80)
    bucket = models.CharField(max_length=80, default="all")
    count = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["interaction_point", "event_type", "bucket"], name="unique_interaction_aggregate"),
        ]

    def __str__(self) -> str:
        return f"{self.interaction_point}:{self.event_type}:{self.bucket}"
