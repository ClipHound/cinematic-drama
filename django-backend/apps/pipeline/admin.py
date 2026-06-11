from django.contrib import admin

from .models import PipelineJob, PipelineStage


class PipelineStageInline(admin.TabularInline):
    model = PipelineStage
    extra = 0
    fields = ("order", "stage_key", "status", "started_at", "finished_at", "error_message")
    readonly_fields = ("started_at", "finished_at")


@admin.action(description="重试失败任务")
def retry_jobs(modeladmin, request, queryset):
    queryset.filter(status=PipelineJob.Status.FAILED).update(status=PipelineJob.Status.QUEUED, error_message="")


@admin.register(PipelineJob)
class PipelineJobAdmin(admin.ModelAdmin):
    list_display = ("id", "job_type", "status", "drama", "episode", "created_at", "updated_at")
    list_filter = ("job_type", "status", "drama")
    search_fields = ("id", "drama__title", "episode__title", "error_message")
    readonly_fields = ("created_at", "updated_at", "started_at", "finished_at")
    inlines = [PipelineStageInline]
    actions = [retry_jobs]


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ("job", "order", "stage_key", "status", "started_at", "finished_at")
    list_filter = ("stage_key", "status")
    search_fields = ("job__id", "stage_key", "error_message")
