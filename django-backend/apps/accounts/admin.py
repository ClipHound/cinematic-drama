from django.contrib import admin

from .models import DeviceUser


@admin.register(DeviceUser)
class DeviceUserAdmin(admin.ModelAdmin):
    list_display = ("device_id", "display_name", "avatar_text", "last_seen_at", "created_at")
    search_fields = ("device_id", "display_name")
    readonly_fields = ("created_at", "last_seen_at")
