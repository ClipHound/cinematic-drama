from django.contrib import admin

from .models import MediaAsset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("asset_type", "owner_type", "owner_id", "mime_type", "size_bytes", "created_at")
    list_filter = ("asset_type", "owner_type")
    search_fields = ("owner_id", "checksum", "url", "file")
    readonly_fields = ("created_at",)
