from django.contrib import admin

from .models import InteractionAggregate, InteractionEvent, InteractionManifest, InteractionPoint


class InteractionPointInline(admin.TabularInline):
    model = InteractionPoint
    extra = 0
    fields = ("point_key", "component", "title", "start_ms", "end_ms", "priority", "sort_order")


@admin.register(InteractionManifest)
class InteractionManifestAdmin(admin.ModelAdmin):
    list_display = ("episode", "version", "status", "duration_ms", "generated_by", "updated_at")
    list_filter = ("status", "generated_by")
    search_fields = ("episode__drama__title", "episode__drama__slug", "source_path")
    readonly_fields = ("created_at", "updated_at")
    inlines = [InteractionPointInline]


@admin.register(InteractionPoint)
class InteractionPointAdmin(admin.ModelAdmin):
    list_display = ("point_key", "component", "title", "manifest", "start_ms", "end_ms", "priority")
    list_filter = ("component", "manifest__episode__drama")
    search_fields = ("point_key", "title", "highlight_reason")


@admin.register(InteractionEvent)
class InteractionEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_type", "device_user", "drama", "episode", "interaction_point", "received_at")
    list_filter = ("event_type", "drama", "episode")
    search_fields = ("event_id", "device_user__device_id", "interaction_point__point_key")
    readonly_fields = ("received_at",)


@admin.register(InteractionAggregate)
class InteractionAggregateAdmin(admin.ModelAdmin):
    list_display = ("interaction_point", "event_type", "bucket", "count", "updated_at")
    list_filter = ("event_type", "bucket")
