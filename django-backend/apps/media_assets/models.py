from __future__ import annotations

from django.db import models


class MediaAsset(models.Model):
    class AssetType(models.TextChoices):
        VIDEO = "video", "Video"
        POSTER = "poster", "Poster"
        COVER = "cover", "Cover"
        FRAME = "frame", "Frame"
        CHARACTER = "character", "Character"
        EVIDENCE = "evidence", "Evidence"
        GENERATED_IMAGE = "generated_image", "Generated image"
        LOTTIE = "lottie", "Lottie"
        OTHER = "other", "Other"

    owner_type = models.CharField(max_length=80)
    owner_id = models.CharField(max_length=80)
    asset_type = models.CharField(max_length=32, choices=AssetType.choices, default=AssetType.OTHER, db_index=True)
    file = models.FileField(upload_to="assets/", blank=True)
    url = models.URLField(blank=True)
    mime_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=128, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["owner_type", "owner_id"]),
            models.Index(fields=["asset_type", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.asset_type}:{self.owner_type}:{self.owner_id}"
