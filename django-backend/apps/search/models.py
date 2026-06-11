from __future__ import annotations

from django.db import models


class SearchDocument(models.Model):
    class ObjectType(models.TextChoices):
        DRAMA = "drama", "Drama"
        EPISODE = "episode", "Episode"
        INTERACTION_POINT = "interaction_point", "Interaction point"

    object_type = models.CharField(max_length=40, choices=ObjectType.choices, db_index=True)
    object_id = models.CharField(max_length=80, db_index=True)
    title = models.CharField(max_length=240)
    body = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    embedding_status = models.CharField(max_length=40, default="pending", db_index=True)
    embedding_vector = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["object_type", "object_id"], name="unique_search_document_object"),
        ]
        indexes = [
            models.Index(fields=["object_type", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.object_type}:{self.title}"
