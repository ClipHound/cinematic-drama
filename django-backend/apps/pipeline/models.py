from __future__ import annotations

from django.db import models


class PipelineJob(models.Model):
    class JobType(models.TextChoices):
        INGEST = "ingest", "Ingest"
        UNDERSTAND = "understand", "Understand"
        INTERACTIONS = "interactions", "Interactions"
        RECREATE = "recreate", "Recreate"
        REINDEX = "reindex", "Reindex"
        TRANSCODE = "transcode", "Transcode"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    job_type = models.CharField(max_length=32, choices=JobType.choices, db_index=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    drama = models.ForeignKey("catalog.Drama", related_name="pipeline_jobs", null=True, blank=True, on_delete=models.SET_NULL)
    episode = models.ForeignKey("catalog.Episode", related_name="pipeline_jobs", null=True, blank=True, on_delete=models.SET_NULL)
    request_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    logs = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["job_type", "status"]),
            models.Index(fields=["drama", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.job_type}:{self.status}:{self.pk}"


class PipelineStage(models.Model):
    class StageStatus(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    job = models.ForeignKey(PipelineJob, related_name="stages", on_delete=models.CASCADE)
    stage_key = models.CharField(max_length=80, db_index=True)
    status = models.CharField(max_length=24, choices=StageStatus.choices, default=StageStatus.QUEUED, db_index=True)
    order = models.PositiveIntegerField(default=0)
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["job", "order"]
        constraints = [
            models.UniqueConstraint(fields=["job", "stage_key"], name="unique_stage_key_per_job"),
        ]

    def __str__(self) -> str:
        return f"{self.job_id}:{self.stage_key}:{self.status}"
