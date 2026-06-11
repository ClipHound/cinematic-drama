from __future__ import annotations

from django.test import TestCase
from django.utils import timezone
from django.conf import settings
from rest_framework.test import APIClient

from apps.analytics.models import Favorite, WatchProgress
from apps.catalog.models import Drama, Episode
from apps.comments.models import Comment
from apps.interactions.models import InteractionEvent, InteractionManifest, InteractionPoint


class PublicApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.drama = Drama.objects.create(
            slug="demo-drama",
            title="测试短剧",
            subtitle="测试副标题",
            description="测试简介",
            status=Drama.Status.PUBLISHED,
            genre_tags=["互动"],
            heat_label="1 集",
            published_at=timezone.now(),
        )
        self.episode = Episode.objects.create(
            drama=self.drama,
            episode_number=1,
            title="第 1 集",
            duration_ms=10000,
            video_status=Episode.VideoStatus.READY,
            manifest_status=Episode.ManifestStatus.READY,
            is_published=True,
        )
        self.manifest = InteractionManifest.objects.create(
            episode=self.episode,
            duration_ms=10000,
            status=InteractionManifest.Status.READY,
            raw_json={"client_hints": {"asset_base_url": "/assets/"}},
        )
        self.point = InteractionPoint.objects.create(
            manifest=self.manifest,
            point_key="ip_test",
            component="celebrate_confetti",
            title="测试互动",
            emotion="happy",
            start_ms=1000,
            end_ms=3000,
            priority=0.8,
            sort_order=1,
        )

    def test_dramas_and_manifest_are_served_from_models(self) -> None:
        response = self.client.get("/api/dramas")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dramas"][0]["id"], "demo-drama")

        response = self.client.get("/api/search", {"q": "互动"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["dramaId"], "demo-drama")

        response = self.client.get("/api/dramas/demo-drama/episodes/1/interactions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["interaction_points"][0]["id"], "ip_test")

    def test_profile_favorites_comments_and_interactions(self) -> None:
        headers = {"HTTP_X_DEVICE_ID": "test-device"}

        response = self.client.get("/api/users/me/profile", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["deviceId"], "test-device")

        response = self.client.put("/api/users/me/favorites/demo-drama", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Favorite.objects.filter(drama=self.drama).exists())

        response = self.client.get("/api/users/me/favorites", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["favorites"][0]["id"], "demo-drama")
        self.assertEqual(response.data["favorites"][0]["firstEpisodeNumber"], 1)
        self.assertIn("favoriteAt", response.data["favorites"][0])

        response = self.client.put(
            f"/api/users/me/progress/{self.episode.id}",
            {"progressMs": 2500, "durationMs": 10000},
            format="json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(WatchProgress.objects.filter(episode=self.episode, progress_ms=2500).exists())

        response = self.client.post(
            "/api/comments",
            {"dramaId": "demo-drama", "episodeNumber": 1, "content": "很好看"},
            format="json",
            **headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(content="很好看").exists())

        payload = {
            "events": [
                {
                    "id": "evt-1",
                    "dramaId": "demo-drama",
                    "episodeNumber": 1,
                    "pointId": "ip_test",
                    "type": "celebrate_click",
                    "actionData": {"tap": 1},
                    "atMs": 1200,
                }
            ]
        }
        response = self.client.post("/api/interactions", payload, format="json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["accepted"], ["evt-1"])
        self.assertEqual(InteractionEvent.objects.count(), 1)

        response = self.client.get("/api/users/me/profile", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["stats"]["watchedEpisodes"], 1)
        self.assertEqual(response.data["stats"]["interactions"], 1)
        self.assertEqual(response.data["stats"]["favorites"], 1)
        self.assertEqual(response.data["continueWatching"]["episodeId"], str(self.episode.id))
        self.assertEqual(response.data["continueWatching"]["progressMs"], 1200)

        response = self.client.get("/api/users/me/history", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["watchProgress"][0]["episodeId"], str(self.episode.id))
        self.assertEqual(response.data["watchProgress"][0]["dramaTitle"], "测试短剧")
        self.assertEqual(response.data["interactions"][0]["pointId"], "ip_test")
        self.assertEqual(response.data["interactions"][0]["pointTitle"], "测试互动")
        self.assertEqual(response.data["interactions"][0]["atMs"], 1200.0)

        response = self.client.post("/api/interactions", payload, format="json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["duplicated"], ["evt-1"])

        unlike_payload = {
            "events": [
                {
                    "id": "evt-unlike",
                    "dramaId": "demo-drama",
                    "episodeNumber": 1,
                    "pointId": "feed-like",
                    "type": "like",
                    "actionData": {"liked": False},
                    "atMs": 1500,
                }
            ]
        }
        response = self.client.post("/api/interactions", unlike_payload, format="json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Favorite.objects.filter(drama=self.drama).exists())

    def test_video_stream_supports_range_requests(self) -> None:
        video_path = settings.MEDIA_ROOT / "test-range-video.mp4"
        video_path.parent.mkdir(parents=True, exist_ok=True)
        video_path.write_bytes(b"0123456789")
        self.episode.source_video_path = str(video_path)
        self.episode.save(update_fields=["source_video_path", "updated_at"])

        response = self.client.get("/api/videos/demo-drama/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Accept-Ranges"], "bytes")

        response = self.client.get("/api/videos/demo-drama/1", HTTP_RANGE="bytes=2-5")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
        self.assertEqual(b"".join(response.streaming_content), b"2345")

        response = self.client.get("/api/videos/demo-drama/1", HTTP_RANGE="bytes=-3")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["Content-Range"], "bytes 7-9/10")
        self.assertEqual(b"".join(response.streaming_content), b"789")
