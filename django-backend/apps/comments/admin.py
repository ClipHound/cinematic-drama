from django.contrib import admin

from .models import Comment


@admin.action(description="隐藏评论")
def hide_comments(modeladmin, request, queryset):
    queryset.update(status=Comment.Status.HIDDEN)


@admin.action(description="恢复可见")
def show_comments(modeladmin, request, queryset):
    queryset.update(status=Comment.Status.VISIBLE)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("content", "device_user", "drama", "episode", "status", "like_count", "created_at")
    list_filter = ("status", "drama", "episode")
    search_fields = ("content", "device_user__device_id", "drama__title")
    actions = [hide_comments, show_comments]
