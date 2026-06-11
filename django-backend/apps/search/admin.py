from django.contrib import admin

from .models import SearchDocument


@admin.register(SearchDocument)
class SearchDocumentAdmin(admin.ModelAdmin):
    list_display = ("object_type", "object_id", "title", "embedding_status", "updated_at")
    list_filter = ("object_type", "embedding_status")
    search_fields = ("title", "body", "object_id")
