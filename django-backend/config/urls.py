from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from . import api


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", api.health),
    path("api/dramas", api.dramas),
    path("api/dramas/<slug:slug>", api.drama_detail),
    path("api/dramas/<slug:slug>/episodes", api.drama_episodes),
    path("api/dramas/<slug:slug>/episodes/<int:number>", api.drama_episode),
    path("api/dramas/<slug:slug>/episodes/<int:number>/interactions", api.episode_manifest),
    path("api/dramas/<slug:slug>/branch-narrative", api.branch_narrative),
    path("api/videos/<slug:slug>/<int:number>", api.video_stream),
    path("api/users/me/profile", api.profile),
    path("api/users/me/history", api.history),
    path("api/users/me/favorites", api.favorites),
    path("api/users/me/favorites/<slug:drama_slug>", api.favorite_detail),
    path("api/users/me/progress/<int:episode_id>", api.update_progress),
    path("api/interactions", api.interactions),
    path("api/interactions/stats/<int:point_id>", api.interaction_stats),
    path("api/episodes/<int:episode_id>/interaction-stats", api.episode_interaction_stats),
    path("api/comments", api.comments),
    path("api/comments/<int:comment_id>", api.comment_detail),
    path("api/search", api.search),
    path("api/ai/search", api.ai_search),
    path("api/ai/chat", api.ai_chat),
    path("api/admin/dramas/upload", api.admin_upload_drama),
    path("api/admin/dramas/<int:drama_id>/publish", api.admin_publish_drama),
    path("api/admin/dramas/<int:drama_id>/unpublish", api.admin_unpublish_drama),
    path("api/admin/pipeline/ingest", api.admin_pipeline_ingest),
    path("api/admin/pipeline/jobs", api.admin_pipeline_jobs),
    path("api/admin/pipeline/jobs/<int:job_id>", api.admin_pipeline_job_detail),
    path("api/admin/pipeline/<int:job_id>/retry", api.admin_pipeline_retry),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
