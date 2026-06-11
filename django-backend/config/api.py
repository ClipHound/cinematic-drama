from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.services import get_device_user
from apps.analytics.models import Favorite, UserActivity, WatchProgress
from apps.catalog.models import Drama, Episode
from apps.comments.models import Comment
from apps.interactions.models import InteractionAggregate, InteractionEvent, InteractionManifest, InteractionPoint
from apps.pipeline.models import PipelineJob, PipelineStage
from apps.search.models import SearchDocument
from apps.search.services import (
    AiProviderError,
    choose_search_query,
    fallback_search_query,
    iter_chat_text,
    public_recommendations,
    reply_uses_recommendations,
    sanitize_chat_reply,
    search_catalog,
)

BASE_DIR = settings.BASE_DIR


def published_dramas():
    return (
        Drama.objects.filter(status=Drama.Status.PUBLISHED)
        .prefetch_related("episodes")
        .order_by("-published_at", "-updated_at")
    )


def visible_episodes(drama: Drama):
    return drama.episodes.filter(is_published=True).order_by("episode_number")


def absolute_media_url(request, field) -> str:
    if field:
        return request.build_absolute_uri(field.url)
    return ""


def poster_or_placeholder(request, drama: Drama, field_name: str) -> str:
    field = getattr(drama, field_name)
    if field:
        return request.build_absolute_uri(field.url)
    label = quote(drama.title[:12] or "互动短剧")
    return (
        "data:image/svg+xml;charset=utf-8,"
        f"%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 400'%3E"
        f"%3Crect width='300' height='400' fill='%23131315'/%3E"
        f"%3Crect x='18' y='18' width='264' height='364' rx='18' fill='%23201f21' stroke='%23494454'/%3E"
        f"%3Ctext x='150' y='194' text-anchor='middle' fill='%23d0bcff' font-size='30' font-family='sans-serif'%3E{label}%3C/text%3E"
        f"%3Ctext x='150' y='232' text-anchor='middle' fill='%23cbc3d7' font-size='18' font-family='sans-serif'%3EPoster pending%3C/text%3E"
        f"%3C/svg%3E"
    )


def episode_item(request, episode: Episode) -> dict[str, Any]:
    total_episodes = visible_episodes(episode.drama).count()
    return {
        "id": str(episode.id),
        "episodeNumber": episode.episode_number,
        "title": episode.title,
        "durationLabel": episode.duration_label,
        "videoUrl": request.build_absolute_uri(f"/api/videos/{episode.drama.slug}/{episode.episode_number}"),
        "thumbnail": request.build_absolute_uri(episode.thumbnail.url) if episode.thumbnail else "",
        "interactionUrl": request.build_absolute_uri(
            f"/api/dramas/{episode.drama.slug}/episodes/{episode.episode_number}/interactions"
        ),
        "totalEpisodes": total_episodes,
        "isLastEpisode": episode.episode_number >= total_episodes,
    }


def search_result_image(request, drama: Drama, episode: Episode | None = None) -> str:
    if episode and episode.thumbnail:
        return request.build_absolute_uri(episode.thumbnail.url)
    if drama.poster:
        return request.build_absolute_uri(drama.poster.url)
    target_episode = episode or visible_episodes(drama).first()
    return request.build_absolute_uri(target_episode.thumbnail.url) if target_episode and target_episode.thumbnail else ""


BRANCH_NARRATIVE_DIR = BASE_DIR / "data" / "branch_narratives"


def drama_has_branch_narrative(drama: Drama) -> bool:
    return (BRANCH_NARRATIVE_DIR / f"{drama.slug}.json").is_file()


def drama_item(request, drama: Drama, *, include_episodes: bool = True) -> dict[str, Any]:
    episodes = list(visible_episodes(drama)) if include_episodes else []
    return {
        "id": drama.slug,
        "title": drama.title,
        "subtitle": drama.subtitle,
        "poster": poster_or_placeholder(request, drama, "poster"),
        "cover": poster_or_placeholder(request, drama, "cover"),
        "genre": drama.genre_tags,
        "heat": drama.heat_label,
        "score": drama.score_label,
        "description": drama.description,
        "episodes": [episode_item(request, episode) for episode in episodes],
        "hasBranchNarrative": drama_has_branch_narrative(drama),
        "totalEpisodes": len(episodes),
    }


def favorite_item(request, favorite: Favorite) -> dict[str, Any]:
    first_episode = visible_episodes(favorite.drama).first()
    return {
        **drama_item(request, favorite.drama, include_episodes=False),
        "favoriteAt": favorite.created_at,
        "firstEpisodeNumber": first_episode.episode_number if first_episode else None,
    }


def manifest_payload(request, manifest: InteractionManifest) -> dict[str, Any]:
    episode = manifest.episode
    points = [
        {
            "id": point.point_key,
            "start_ms": point.start_ms,
            "end_ms": point.end_ms,
            "component": point.component,
            "title": point.title,
            "emotion": point.emotion,
            "priority": point.priority,
            "highlight_reason": point.highlight_reason,
            "config": point.config,
        }
        for point in manifest.points.all().order_by("sort_order", "start_ms")
    ]
    payload = dict(manifest.raw_json or {})
    payload.update(
        {
            "drama_id": episode.drama.slug,
            "episode_id": f"ep_{episode.episode_number:03d}",
            "title": f"{episode.drama.title} · {episode.title}",
            "video_url": request.build_absolute_uri(f"/api/videos/{episode.drama.slug}/{episode.episode_number}"),
            "duration_ms": manifest.duration_ms or episode.duration_ms,
            "manifest_version": manifest.version,
            "client_hints": {
                **dict(payload.get("client_hints") or {}),
                "asset_base_url": "/assets/",
                "ws_enabled": False,
            },
            "interaction_points": points,
        }
    )
    return payload


@api_view(["GET"])
def health(request):
    return Response({"status": "ok", "backend": "django"})


@api_view(["GET"])
def dramas(request):
    return Response({"dramas": [drama_item(request, drama) for drama in published_dramas()]})


@api_view(["GET"])
def drama_detail(request, slug: str):
    drama = get_object_or_404(published_dramas(), slug=slug)
    return Response(drama_item(request, drama))


@api_view(["GET"])
def drama_episodes(request, slug: str):
    drama = get_object_or_404(published_dramas(), slug=slug)
    return Response({"episodes": [episode_item(request, episode) for episode in visible_episodes(drama)]})


@api_view(["GET"])
def drama_episode(request, slug: str, number: int):
    drama = get_object_or_404(published_dramas(), slug=slug)
    episode = get_object_or_404(visible_episodes(drama), episode_number=number)
    return Response(episode_item(request, episode))


@api_view(["GET"])
def episode_manifest(request, slug: str, number: int):
    drama = get_object_or_404(published_dramas(), slug=slug)
    episode = get_object_or_404(visible_episodes(drama), episode_number=number)
    manifest = get_object_or_404(
        InteractionManifest.objects.prefetch_related("points"),
        episode=episode,
        status=InteractionManifest.Status.READY,
    )
    return Response(manifest_payload(request, manifest))


@api_view(["GET"])
def branch_narrative(request, slug: str):
    drama = get_object_or_404(published_dramas(), slug=slug)
    file_path = BRANCH_NARRATIVE_DIR / f"{drama.slug}.json"
    if not file_path.is_file():
        raise Http404("branch narrative not found")
    with file_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return Response(data)


@api_view(["GET", "HEAD"])
def video_stream(request, slug: str, number: int):
    drama = get_object_or_404(published_dramas(), slug=slug)
    episode = get_object_or_404(visible_episodes(drama), episode_number=number)
    if episode.video_file:
        path = Path(episode.video_file.path)
    elif episode.source_video_path:
        path = Path(episode.source_video_path)
    else:
        raise Http404("video file missing")
    if not path.exists():
        raise Http404("video file missing")
    file_size = path.stat().st_size
    range_header = request.headers.get("Range", "")
    if range_header.startswith("bytes="):
        try:
            start_text, end_text = range_header.removeprefix("bytes=").split("-", 1)
            if not start_text and not end_text:
                raise ValueError
            if start_text:
                start = int(start_text)
                end = int(end_text) if end_text else file_size - 1
            else:
                suffix_length = int(end_text)
                start = max(file_size - suffix_length, 0)
                end = file_size - 1
        except ValueError:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        if start >= file_size or end < start:
            return HttpResponse(status=416, headers={"Content-Range": f"bytes */{file_size}"})
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_file():
            with path.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingHttpResponse(
            iter_file(),
            status=206,
            content_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
                "Content-Range": f"bytes {start}-{end}/{file_size}",
            },
        )
    return FileResponse(
        path.open("rb"),
        content_type="video/mp4",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )


@api_view(["GET"])
def profile(request):
    user = get_device_user(request)
    latest = WatchProgress.objects.filter(device_user=user).select_related("drama", "episode").first()
    return Response(
        {
            "deviceId": user.device_id,
            "displayName": user.display_name,
            "bio": "基于设备 ID 的互动档案",
            "avatarText": user.avatar_text,
            "stats": {
                "watchedEpisodes": WatchProgress.objects.filter(device_user=user).count(),
                "interactions": InteractionEvent.objects.filter(device_user=user).count(),
                "favorites": Favorite.objects.filter(device_user=user).count(),
            },
            "continueWatching": {
                "episodeId": str(latest.episode.id),
                "dramaId": latest.drama.slug,
                "episodeNumber": latest.episode.episode_number,
                "title": f"{latest.drama.title} · {latest.episode.title}",
                "progressMs": latest.progress_ms,
                "durationMs": latest.duration_ms,
            }
            if latest
            else None,
        }
    )


@api_view(["GET"])
def history(request):
    user = get_device_user(request)
    progress = WatchProgress.objects.filter(device_user=user).select_related("drama", "episode")[:50]
    events = InteractionEvent.objects.filter(device_user=user).select_related("drama", "episode", "interaction_point")[:50]
    return Response(
        {
            "watchProgress": [
                {
                    "episodeId": str(item.episode.id),
                    "dramaId": item.drama.slug,
                    "dramaTitle": item.drama.title,
                    "episodeNumber": item.episode.episode_number,
                    "episodeTitle": item.episode.title,
                    "title": f"{item.drama.title} · {item.episode.title}",
                    "progressMs": item.progress_ms,
                    "durationMs": item.duration_ms,
                    "updatedAt": item.updated_at,
                }
                for item in progress
            ],
            "interactions": [
                {
                    "eventId": event.event_id,
                    "eventType": event.event_type,
                    "dramaId": event.drama.slug,
                    "dramaTitle": event.drama.title,
                    "episodeNumber": event.episode.episode_number,
                    "episodeTitle": event.episode.title,
                    "pointId": event.interaction_point.point_key if event.interaction_point else None,
                    "pointTitle": event.interaction_point.title if event.interaction_point else None,
                    "atMs": event.at_ms,
                    "actionData": event.action_data,
                    "receivedAt": event.received_at,
                }
                for event in events
            ],
        }
    )


@api_view(["GET"])
def favorites(request):
    user = get_device_user(request)
    rows = Favorite.objects.filter(device_user=user).select_related("drama")
    return Response({"favorites": [favorite_item(request, favorite) for favorite in rows]})


@api_view(["PUT", "DELETE"])
def favorite_detail(request, drama_slug: str):
    user = get_device_user(request)
    drama = get_object_or_404(Drama, slug=drama_slug)
    if request.method == "PUT":
        Favorite.objects.get_or_create(device_user=user, drama=drama)
        UserActivity.objects.create(device_user=user, activity_type="favorite", drama=drama)
        return Response({"status": "ok", "favorited": True})
    Favorite.objects.filter(device_user=user, drama=drama).delete()
    UserActivity.objects.create(device_user=user, activity_type="unfavorite", drama=drama)
    return Response({"status": "ok", "favorited": False})


@api_view(["PUT"])
def update_progress(request, episode_id: int):
    user = get_device_user(request)
    episode = get_object_or_404(Episode.objects.select_related("drama"), pk=episode_id)
    progress, _ = WatchProgress.objects.update_or_create(
        device_user=user,
        episode=episode,
        defaults={
            "drama": episode.drama,
            "progress_ms": int(request.data.get("progress_ms") or request.data.get("progressMs") or 0),
            "duration_ms": int(request.data.get("duration_ms") or request.data.get("durationMs") or episode.duration_ms),
        },
    )
    UserActivity.objects.create(device_user=user, activity_type="watch_progress", drama=episode.drama, episode=episode)
    return Response({"status": "ok", "id": progress.id})


def parse_client_timestamp(value: str | None):
    if not value:
        return None
    parsed = timezone.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else timezone.make_aware(parsed)


@api_view(["POST"])
def interactions(request):
    user = get_device_user(request)
    events = request.data.get("events") if isinstance(request.data, dict) else None
    if not isinstance(events, list):
        events = [request.data]
    accepted: list[str] = []
    duplicated: list[str] = []
    rejected: list[dict[str, str]] = []
    for event in events:
        event_id = str(event.get("id") or event.get("event_id") or "")
        if not event_id:
            rejected.append({"event_id": "", "reason": "missing event id"})
            continue
        if InteractionEvent.objects.filter(event_id=event_id).exists():
            duplicated.append(event_id)
            continue
        try:
            drama = Drama.objects.get(slug=str(event.get("dramaId") or event.get("drama_id") or ""))
            episode = Episode.objects.get(drama=drama, episode_number=int(event.get("episodeNumber") or 0))
        except (Drama.DoesNotExist, Episode.DoesNotExist, ValueError):
            rejected.append({"event_id": event_id, "reason": "invalid drama or episode"})
            continue

        point = None
        point_id = str(event.get("pointId") or event.get("point_id") or "")
        if point_id and not point_id.startswith("feed-"):
            point = InteractionPoint.objects.filter(manifest__episode=episode, point_key=point_id).first()
            if point is None:
                rejected.append({"event_id": event_id, "reason": "invalid point"})
                continue

        try:
            with transaction.atomic():
                row = InteractionEvent.objects.create(
                    event_id=event_id,
                    device_user=user,
                    drama=drama,
                    episode=episode,
                    interaction_point=point,
                    event_type=str(event.get("type") or event.get("event_type") or "interaction"),
                    action_data=event.get("actionData") if isinstance(event.get("actionData"), dict) else {},
                    at_ms=float(event.get("atMs") or event.get("at_ms") or 0),
                    client_timestamp=parse_client_timestamp(event.get("createdAt") or event.get("client_timestamp")),
                )
                WatchProgress.objects.update_or_create(
                    device_user=user,
                    episode=episode,
                    defaults={"drama": drama, "progress_ms": int(row.at_ms), "duration_ms": episode.duration_ms},
                )
                UserActivity.objects.create(
                    device_user=user,
                    activity_type=row.event_type,
                    drama=drama,
                    episode=episode,
                    payload={"event_id": event_id},
                )
                if row.event_type == "like":
                    liked = row.action_data.get("liked")
                    if liked is False:
                        Favorite.objects.filter(device_user=user, drama=drama).delete()
                    else:
                        Favorite.objects.get_or_create(device_user=user, drama=drama)
                if point:
                    aggregate, _ = InteractionAggregate.objects.get_or_create(
                        interaction_point=point,
                        event_type=row.event_type,
                        bucket="all",
                    )
                    aggregate.count += 1
                    aggregate.save(update_fields=["count", "updated_at"])
            accepted.append(event_id)
        except IntegrityError:
            duplicated.append(event_id)
    return Response({"accepted": accepted, "duplicated": duplicated, "rejected": rejected})


@api_view(["GET"])
def interaction_stats(request, point_id: int):
    point = get_object_or_404(InteractionPoint, pk=point_id)
    aggregates = point.aggregates.all()
    return Response({"pointId": point.id, "stats": [{"eventType": item.event_type, "bucket": item.bucket, "count": item.count, "payload": item.payload} for item in aggregates]})


@api_view(["GET"])
def episode_interaction_stats(request, episode_id: int):
    episode = get_object_or_404(Episode, pk=episode_id)
    points = InteractionPoint.objects.filter(manifest__episode=episode).annotate(event_count=Count("events"))
    return Response({"episodeId": episode.id, "points": [{"id": point.id, "pointKey": point.point_key, "eventCount": point.event_count} for point in points]})


@api_view(["GET", "POST"])
def comments(request):
    user = get_device_user(request)
    if request.method == "GET":
        drama_slug = request.query_params.get("drama")
        episode_number = request.query_params.get("episode")
        rows = Comment.objects.filter(status=Comment.Status.VISIBLE).select_related("device_user", "drama", "episode")
        if drama_slug:
            rows = rows.filter(drama__slug=drama_slug)
        if episode_number:
            rows = rows.filter(episode__episode_number=int(episode_number))
        return Response(
            {
                "comments": [
                    {
                        "id": item.id,
                        "deviceId": item.device_user.device_id,
                        "displayName": item.device_user.display_name,
                        "dramaId": item.drama.slug,
                        "episodeNumber": item.episode.episode_number if item.episode else None,
                        "content": item.content,
                        "likeCount": item.like_count,
                        "createdAt": item.created_at,
                    }
                    for item in rows[:100]
                ]
            }
        )
    drama = get_object_or_404(Drama, slug=str(request.data.get("drama") or request.data.get("dramaId") or ""))
    episode = None
    if request.data.get("episode") or request.data.get("episodeNumber"):
        episode = get_object_or_404(Episode, drama=drama, episode_number=int(request.data.get("episode") or request.data.get("episodeNumber")))
    content = str(request.data.get("content") or "").strip()
    if not content:
        return Response({"status": "error", "message": "content required"}, status=400)
    comment = Comment.objects.create(device_user=user, drama=drama, episode=episode, content=content)
    UserActivity.objects.create(device_user=user, activity_type="comment", drama=drama, episode=episode, payload={"comment_id": comment.id})
    return Response({"status": "ok", "id": comment.id})


@api_view(["DELETE"])
def comment_detail(request, comment_id: int):
    user = get_device_user(request)
    comment = get_object_or_404(Comment, pk=comment_id, device_user=user)
    comment.status = Comment.Status.DELETED
    comment.save(update_fields=["status", "updated_at"])
    return Response({"status": "ok"})


def search_results(request, query: str):
    docs = SearchDocument.objects.filter(Q(title__icontains=query) | Q(body__icontains=query) | Q(tags__icontains=query))[:20]
    results = []
    for doc in docs:
        result = {"type": doc.object_type, "title": doc.title, "snippet": doc.body[:160]}
        if doc.object_type == SearchDocument.ObjectType.DRAMA:
            drama = Drama.objects.filter(pk=doc.object_id).first()
            if drama:
                result.update({"dramaId": drama.slug, "subtitle": drama.subtitle, "poster": search_result_image(request, drama)})
        elif doc.object_type == SearchDocument.ObjectType.EPISODE:
            episode = Episode.objects.filter(pk=doc.object_id).select_related("drama").first()
            if episode:
                result.update({"dramaId": episode.drama.slug, "episodeNumber": episode.episode_number, "poster": search_result_image(request, episode.drama, episode)})
        results.append(result)
    if results:
        return results
    dramas_qs = list(published_dramas().filter(
        Q(slug__icontains=query)
        | Q(title__icontains=query)
        | Q(subtitle__icontains=query)
        | Q(description__icontains=query)
    )[:20])
    seen_drama_ids = {drama.id for drama in dramas_qs}
    query_text = query.casefold()
    for drama in published_dramas():
        if len(dramas_qs) >= 20:
            break
        if drama.id in seen_drama_ids:
            continue
        genre_text = " ".join(str(tag) for tag in (drama.genre_tags or [])).casefold()
        if query_text not in genre_text:
            continue
        dramas_qs.append(drama)
        seen_drama_ids.add(drama.id)
    return [
        {
            "type": "drama",
            "dramaId": drama.slug,
            "title": drama.title,
            "subtitle": drama.subtitle,
            "snippet": drama.description[:160],
            "poster": search_result_image(request, drama),
        }
        for drama in dramas_qs[:20]
    ]


@api_view(["GET"])
def search(request):
    query = str(request.query_params.get("q") or "").strip()
    return Response({"results": search_results(request, query) if query else []})


@api_view(["POST"])
def ai_search(request):
    query = str(request.data.get("query") or "").strip()
    recommendations = search_catalog(request, query, limit=20) if query else []
    public_items = public_recommendations(recommendations)
    results = [
        {
            "type": item.get("type"),
            "dramaId": item.get("dramaId"),
            "episodeNumber": item.get("episodeNumber"),
            "title": item.get("title"),
            "subtitle": item.get("subtitle"),
            "snippet": item.get("reason"),
            "poster": item.get("imageUrl"),
        }
        for item in public_items
    ]
    return Response({"status": "ok", "message": f"找到 {len(results)} 个相关结果。", "results": results})


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@api_view(["POST"])
def ai_chat(request):
    raw_messages = request.data.get("messages") if isinstance(request.data, dict) else None
    mode = str(request.data.get("mode") or "fast").strip().casefold() if isinstance(request.data, dict) else "fast"
    if mode not in {"fast", "smart"}:
        mode = "fast"
    if not isinstance(raw_messages, list):
        raw_messages = []
    messages = [
        {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "").strip()}
        for item in raw_messages
        if isinstance(item, dict) and str(item.get("content") or "").strip()
    ]
    query = next((item["content"] for item in reversed(messages) if item["role"] == "user"), "")

    def event_stream():
        yield sse_event("message_start", {"status": "ok", "mode": mode})
        if not query:
            yield sse_event("error", {"message": "请输入想搜索的剧情或剧名。"})
            yield sse_event("message_end", {"status": "error"})
            return

        if mode == "fast":
            yield sse_event("progress", {"message": "正在快速匹配需求"})
            if settings.AI_CHAT_API_KEY and settings.AI_CHAT_MODEL:
                search_query, planned_by_model, direct_response = query, False, ""
            else:
                search_query, planned_by_model, direct_response = fallback_search_query(messages), False, ""
        else:
            yield sse_event("progress", {"message": "正在理解你的需求"})
            try:
                search_query, planned_by_model, direct_response = choose_search_query(messages)
            except AiProviderError:
                search_query, planned_by_model, direct_response = fallback_search_query(messages), False, ""

        if direct_response and not search_query:
            yield sse_event("text_delta", {"text": direct_response})
            yield sse_event("message_end", {"status": "ok"})
            return

        recommendations = []
        if search_query:
            yield sse_event("tool_call_start", {"toolName": "search_catalog", "query": search_query, "plannedByModel": planned_by_model})
            recommendations = search_catalog(request, search_query, limit=3)
            yield sse_event("tool_call_result", {"toolName": "search_catalog", "count": len(recommendations)})
            yield sse_event("progress", {"message": "正在整理回复" if recommendations else "正在生成回复"})
        else:
            yield sse_event("progress", {"message": "正在生成回复"})

        try:
            chunks = []
            for chunk in iter_chat_text(messages, recommendations):
                chunks.append(chunk)
            raw_reply_text = "".join(chunks)
            used_recommendations = reply_uses_recommendations(raw_reply_text, recommendations) if recommendations else False
            reply_text = sanitize_chat_reply(raw_reply_text) if used_recommendations else raw_reply_text
            if reply_text:
                yield sse_event("text_delta", {"text": reply_text})
        except AiProviderError:
            if recommendations:
                yield sse_event("text_delta", {"text": "可以先看下面这些推荐，题材和剧情节奏更贴近你的需求。"})
                used_recommendations = True
            else:
                fallback = "回复暂时不可用，请稍后再试。"
                yield sse_event("error", {"message": fallback})
                yield sse_event("text_delta", {"text": fallback})
        if recommendations and used_recommendations:
            yield sse_event("recommendations", {"items": public_recommendations(recommendations, limit=3)})
        yield sse_event("message_end", {"status": "ok"})

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@api_view(["POST"])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def admin_upload_drama(request):
    title = str(request.data.get("title") or "").strip()
    slug = str(request.data.get("slug") or "").strip()
    if not title or not slug:
        return Response({"status": "error", "message": "title and slug required"}, status=400)
    drama, _ = Drama.objects.get_or_create(slug=slug, defaults={"title": title})
    drama.title = title
    drama.subtitle = str(request.data.get("subtitle") or drama.subtitle)
    drama.description = str(request.data.get("description") or drama.description)
    drama.status = Drama.Status.DRAFT
    if request.FILES.get("poster"):
        drama.poster = request.FILES["poster"]
    if request.FILES.get("cover"):
        drama.cover = request.FILES["cover"]
    drama.save()
    videos = request.FILES.getlist("videos")
    for index, video in enumerate(videos, start=1):
        Episode.objects.update_or_create(
            drama=drama,
            episode_number=index,
            defaults={
                "title": f"第 {index} 集",
                "video_file": video,
                "video_status": Episode.VideoStatus.UPLOADED,
                "is_published": False,
            },
        )
    job = create_ingest_job(drama)
    return Response({"status": "ok", "dramaId": drama.id, "jobId": job.id})


def create_ingest_job(drama: Drama) -> PipelineJob:
    job = PipelineJob.objects.create(job_type=PipelineJob.JobType.INGEST, status=PipelineJob.Status.QUEUED, drama=drama)
    for order, key in enumerate(["upload", "project_init", "understand", "interaction_design", "manifest_import", "search_index", "publish_ready"], start=1):
        PipelineStage.objects.create(job=job, order=order, stage_key=key)
    return job


@api_view(["POST"])
def admin_publish_drama(request, drama_id: int):
    drama = get_object_or_404(Drama, pk=drama_id)
    drama.publish()
    drama.save(update_fields=["status", "published_at", "updated_at"])
    drama.episodes.update(is_published=True, video_status=Episode.VideoStatus.READY)
    return Response({"status": "ok"})


@api_view(["POST"])
def admin_unpublish_drama(request, drama_id: int):
    drama = get_object_or_404(Drama, pk=drama_id)
    drama.status = Drama.Status.READY
    drama.save(update_fields=["status", "updated_at"])
    return Response({"status": "ok"})


@api_view(["POST"])
def admin_pipeline_ingest(request):
    drama = get_object_or_404(Drama, pk=int(request.data.get("drama_id") or request.data.get("dramaId")))
    job = create_ingest_job(drama)
    return Response({"status": "ok", "jobId": job.id})


@api_view(["GET"])
def admin_pipeline_jobs(request):
    jobs = PipelineJob.objects.select_related("drama", "episode")[:100]
    return Response({"jobs": [job_payload(job) for job in jobs]})


@api_view(["GET"])
def admin_pipeline_job_detail(request, job_id: int):
    return Response(job_payload(get_object_or_404(PipelineJob.objects.prefetch_related("stages"), pk=job_id), include_stages=True))


@api_view(["POST"])
def admin_pipeline_retry(request, job_id: int):
    job = get_object_or_404(PipelineJob, pk=job_id)
    job.status = PipelineJob.Status.QUEUED
    job.error_message = ""
    job.finished_at = None
    job.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
    job.stages.filter(status=PipelineStage.StageStatus.FAILED).update(status=PipelineStage.StageStatus.QUEUED, error_message="")
    return Response({"status": "ok", "jobId": job.id})


def job_payload(job: PipelineJob, *, include_stages: bool = False) -> dict[str, Any]:
    payload = {
        "id": job.id,
        "jobType": job.job_type,
        "status": job.status,
        "dramaId": job.drama_id,
        "episodeId": job.episode_id,
        "errorMessage": job.error_message,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
    }
    if include_stages:
        payload["stages"] = [
            {
                "id": stage.id,
                "stageKey": stage.stage_key,
                "status": stage.status,
                "order": stage.order,
                "errorMessage": stage.error_message,
            }
            for stage in job.stages.all()
        ]
    return payload
