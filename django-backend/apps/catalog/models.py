from __future__ import annotations

from django.db import models
from django.utils import timezone


class Drama(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"
        FAILED = "failed", "Failed"

    slug = models.SlugField(max_length=128, unique=True)
    title = models.CharField(max_length=160)
    subtitle = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    genre_tags = models.JSONField(default=list, blank=True)
    score_label = models.CharField(max_length=40, default="暂无评分")
    heat_label = models.CharField(max_length=40, default="0 集")
    poster = models.ImageField(upload_to="posters/", blank=True)
    cover = models.ImageField(upload_to="covers/", blank=True)
    source = models.CharField(max_length=80, default="admin")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-updated_at"]

    def publish(self) -> None:
        self.status = self.Status.PUBLISHED
        self.published_at = self.published_at or timezone.now()

    def __str__(self) -> str:
        return self.title


class Episode(models.Model):
    class VideoStatus(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    class ManifestStatus(models.TextChoices):
        MISSING = "missing", "Missing"
        GENERATING = "generating", "Generating"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    drama = models.ForeignKey(Drama, related_name="episodes", on_delete=models.CASCADE)
    episode_number = models.PositiveIntegerField()
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    video_file = models.FileField(upload_to="videos/", blank=True)
    source_video_path = models.CharField(max_length=600, blank=True)
    video_status = models.CharField(max_length=24, choices=VideoStatus.choices, default=VideoStatus.UPLOADED, db_index=True)
    manifest_status = models.CharField(max_length=24, choices=ManifestStatus.choices, default=ManifestStatus.MISSING, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["drama__slug", "episode_number"]
        constraints = [
            models.UniqueConstraint(fields=["drama", "episode_number"], name="unique_episode_number_per_drama"),
        ]

    @property
    def duration_label(self) -> str:
        if self.duration_ms <= 0:
            return "--:--"
        total_seconds = round(self.duration_ms / 1000)
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    def __str__(self) -> str:
        return f"{self.drama.title} 第 {self.episode_number} 集"
