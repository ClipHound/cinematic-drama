from __future__ import annotations

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.models import Favorite
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

        response = self.client.post("/api/interactions", payload, format="json", **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["duplicated"], ["evt-1"])
