from django.contrib import admin

from .models import Drama, Episode


class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 0
    fields = ("episode_number", "title", "duration_ms", "video_status", "manifest_status", "is_published")


@admin.action(description="发布所选剧目")
def publish_dramas(modeladmin, request, queryset):
    for drama in queryset:
        drama.publish()
        drama.save(update_fields=["status", "published_at", "updated_at"])


@admin.action(description="下架所选剧目")
def unpublish_dramas(modeladmin, request, queryset):
    queryset.update(status=Drama.Status.READY)


@admin.register(Drama)
class DramaAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "status", "heat_label", "score_label", "published_at", "updated_at")
    list_filter = ("status", "source")
    search_fields = ("title", "slug", "subtitle")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [EpisodeInline]
    actions = [publish_dramas, unpublish_dramas]


@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ("drama", "episode_number", "title", "video_status", "manifest_status", "is_published", "duration_ms")
    list_filter = ("video_status", "manifest_status", "is_published", "drama")
    search_fields = ("title", "drama__title", "drama__slug")
    ordering = ("drama__slug", "episode_number")
