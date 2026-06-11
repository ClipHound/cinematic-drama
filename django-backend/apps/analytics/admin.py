from django.contrib import admin

from .models import Favorite, UserActivity, WatchProgress


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("device_user", "drama", "created_at")
    list_filter = ("drama",)
    search_fields = ("device_user__device_id", "drama__title", "drama__slug")


@admin.register(WatchProgress)
class WatchProgressAdmin(admin.ModelAdmin):
    list_display = ("device_user", "drama", "episode", "progress_ms", "duration_ms", "updated_at")
    list_filter = ("drama", "episode")
    search_fields = ("device_user__device_id", "drama__title")


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ("device_user", "activity_type", "drama", "episode", "created_at")
    list_filter = ("activity_type", "drama")
    search_fields = ("device_user__device_id", "activity_type", "drama__title")
