from __future__ import annotations

import json
import tempfile
import zipfile
from urllib import error
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.catalog.models import Drama, Episode
from apps.search.models import SearchDocument
from apps.search import services
from apps.search.services import choose_search_query, cosine_similarity, embed_text, sanitize_chat_reply, search_catalog
from config import api as config_api


class SearchAiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.drama = Drama.objects.create(
            slug="demo-ai",
            title="测试 AI 短剧",
            subtitle="古装权谋",
            description="皇帝和公主卷入高燃反转。",
            status=Drama.Status.PUBLISHED,
            genre_tags=["古装", "权谋", "互动"],
            score_label="9.1",
            heat_label="1 集",
            published_at=timezone.now(),
        )
        self.episode = Episode.objects.create(
            drama=self.drama,
            episode_number=1,
            title="第 1 集",
            description="比武招亲出现神秘高手。",
            duration_ms=10000,
            thumbnail="thumbnails/demo-ai/ep_001.jpg",
            video_status=Episode.VideoStatus.READY,
            is_published=True,
        )
        SearchDocument.objects.create(
            object_type=SearchDocument.ObjectType.EPISODE,
            object_id=str(self.episode.id),
            title="测试 AI 短剧 第 1 集",
            body="比武招亲 神秘高手 高燃反转",
            tags=["古装", "权谋"],
            embedding_status="ready",
            embedding_vector=[1.0, 0.0, 0.0],
        )
        SearchDocument.objects.create(
            object_type=SearchDocument.ObjectType.DRAMA,
            object_id=str(self.drama.id),
            title="测试 AI 短剧",
            body="皇帝 公主 古装权谋",
            tags=["互动"],
            embedding_status="ready",
            embedding_vector=[0.0, 1.0, 0.0],
        )

    def test_cosine_similarity(self) -> None:
        self.assertEqual(cosine_similarity([1, 0], [1, 0]), 1)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0)

    @override_settings(AI_CHAT_API_KEY="", AI_CHAT_MODEL="")
    def test_choose_search_query_falls_back_to_latest_user_message(self) -> None:
        query, planned, direct_response = choose_search_query(
            [
                {"role": "user", "content": "第一句"},
                {"role": "assistant", "content": "回复"},
                {"role": "user", "content": "找古装权谋爽剧"},
            ]
        )
        self.assertEqual(query, "找古装权谋爽剧")
        self.assertFalse(planned)
        self.assertEqual(direct_response, "")

    @override_settings(AI_CHAT_API_KEY="chat-key", AI_CHAT_MODEL="chat-model")
    def test_choose_search_query_skips_search_when_model_does_not_call_tool(self) -> None:
        original = services._post_json
        services._post_json = lambda *args, **kwargs: {
            "choices": [{"message": {"content": "你好，有什么想聊的？"}}]
        }
        try:
            query, planned, direct_response = choose_search_query([{"role": "user", "content": "你好"}])
        finally:
            services._post_json = original

        self.assertIsNone(query)
        self.assertTrue(planned)
        self.assertEqual(direct_response, "你好，有什么想聊的？")

    @override_settings(AI_CHAT_API_KEY="chat-key", AI_CHAT_MODEL="chat-model")
    def test_choose_search_query_uses_model_tool_query(self) -> None:
        original = services._post_json
        services._post_json = lambda *args, **kwargs: {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "search_catalog",
                                    "arguments": json.dumps({"query": "女主复仇 高燃反转"}, ensure_ascii=False),
                                }
                            }
                        ]
                    }
                }
            ]
        }
        try:
            query, planned, direct_response = choose_search_query([{"role": "user", "content": "推荐女主复仇的爽剧"}])
        finally:
            services._post_json = original

        self.assertEqual(query, "女主复仇 高燃反转")
        self.assertTrue(planned)
        self.assertEqual(direct_response, "")

    @override_settings(AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_search_catalog_falls_back_to_safe_catalog_results(self) -> None:
        results = search_catalog(self.client.request().wsgi_request, "古装", limit=3)
        self.assertTrue(results)
        self.assertTrue(results[0]["href"].startswith("/"))
        self.assertIn(results[0]["type"], {"drama", "episode"})
        self.assertTrue(results[0]["imageUrl"])

    def test_sanitize_chat_reply_removes_technical_retrieval_details(self) -> None:
        text = "根据剧库检索结果，为您推荐《测试 AI 短剧》。\n1. **第 1 集**（相似度0.57）：剧情高燃。\n评分：0.92"
        cleaned = sanitize_chat_reply(text)
        self.assertNotIn("检索结果", cleaned)
        self.assertNotIn("相似度", cleaned)
        self.assertNotIn("评分", cleaned)
        self.assertNotIn("0.57", cleaned)
        self.assertIn("《测试 AI 短剧》", cleaned)
        self.assertIn("剧情高燃", cleaned)

    def test_episode_search_result_uses_persisted_video_thumbnail(self) -> None:
        self.drama.poster.name = "posters/demo-ai.jpg"
        self.drama.save(update_fields=["poster", "updated_at"])
        document = SearchDocument.objects.get(object_type=SearchDocument.ObjectType.EPISODE)
        response = self.client.get("/api/search", {"q": document.title})

        self.assertEqual(response.status_code, 200)
        episode_result = next(item for item in response.data["results"] if item["type"] == "episode")
        self.assertEqual(
            episode_result["poster"],
            "http://testserver/media/thumbnails/demo-ai/ep_001.jpg",
        )

    @override_settings(
        AI_EMBEDDING_BASE_URL="https://example.test/v1",
        AI_EMBEDDING_API_KEY="embedding-key",
        AI_EMBEDDING_MODEL="embedding-model",
        AI_EMBEDDING_DIMENSIONS=1024,
    )
    def test_embed_text_sends_optional_dimensions(self) -> None:
        captured = {}

        def fake_post_json(url, api_key, payload, *, timeout=None):
            captured.update({"url": url, "api_key": api_key, "payload": payload})
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

        original = services._post_json
        services._post_json = fake_post_json
        try:
            self.assertEqual(embed_text("测试文本"), [0.1, 0.2, 0.3])
        finally:
            services._post_json = original

        self.assertEqual(captured["url"], "https://example.test/v1/embeddings")
        self.assertEqual(captured["api_key"], "embedding-key")
        self.assertEqual(captured["payload"]["model"], "embedding-model")
        self.assertEqual(captured["payload"]["input"], "测试文本")
        self.assertEqual(captured["payload"]["dimensions"], 1024)

    @override_settings(AI_HTTP_MAX_RETRIES=1, AI_HTTP_RETRY_BASE_SECONDS=0)
    def test_post_json_retries_transient_provider_errors(self) -> None:
        calls = {"count": 0}

        class FakeHttpError(error.HTTPError):
            def read(self):
                return b"rate limited"

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"ok": true}'

        def fake_urlopen(req, timeout=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise FakeHttpError("https://example.test", 429, "Too Many Requests", {}, None)
            return FakeResponse()

        original = services.request.urlopen
        services.request.urlopen = fake_urlopen
        try:
            self.assertEqual(services._post_json("https://example.test", "", {}), {"ok": True})
        finally:
            services.request.urlopen = original
        self.assertEqual(calls["count"], 2)

    @override_settings(AI_CHAT_API_KEY="", AI_CHAT_MODEL="", AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_ai_chat_stream_returns_recommendations_and_text(self) -> None:
        response = self.client.post(
            "/api/ai/chat",
            {"messages": [{"role": "user", "content": "找古装权谋"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: message_start", body)
        self.assertIn('"mode": "fast"', body)
        self.assertIn("正在快速匹配需求", body)
        self.assertIn("event: tool_call_start", body)
        self.assertIn("event: text_delta", body)
        self.assertIn("event: recommendations", body)
        self.assertLess(body.index("event: text_delta"), body.index("event: recommendations"))
        self.assertIn("/detail?drama=demo-ai", body)
        recommendation_block = next(part for part in body.split("\n\n") if part.startswith("event: recommendations"))
        recommendation_payload = json.loads(
            next(line for line in recommendation_block.splitlines() if line.startswith("data: ")).removeprefix("data: ")
        )
        self.assertLessEqual(len(recommendation_payload["items"]), 3)
        self.assertNotIn("score", recommendation_payload["items"][0])
        self.assertNotIn("相似度", recommendation_payload["items"][0]["reason"])
        self.assertNotIn("关键词匹配", recommendation_payload["items"][0]["reason"])
        self.assertIn("event: message_end", body)

    @override_settings(AI_CHAT_API_KEY="", AI_CHAT_MODEL="", AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_ai_chat_smart_mode_shows_planning_progress(self) -> None:
        response = self.client.post(
            "/api/ai/chat",
            {"mode": "smart", "messages": [{"role": "user", "content": "找古装权谋"}]},
            format="json",
        )
        body = b"".join(response.streaming_content).decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('"mode": "smart"', body)
        self.assertIn("正在理解你的需求", body)
        self.assertIn("event: tool_call_start", body)

    @override_settings(AI_CHAT_API_KEY="chat-key", AI_CHAT_MODEL="chat-model", AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_ai_chat_fast_mode_attaches_candidates_but_hides_unused_cards(self) -> None:
        captured = {}
        fake_recommendation = {
            "type": "drama",
            "id": "drama:demo",
            "dramaId": "demo-ai",
            "episodeNumber": None,
            "title": "测试 AI 短剧",
            "subtitle": "古装权谋",
            "reason": "题材和剧情方向更贴近你的需求。",
            "imageUrl": "http://testserver/poster.jpg",
            "href": "/detail?drama=demo-ai",
            "score": 0.8,
        }
        original_choose = config_api.choose_search_query
        original_iter = config_api.iter_chat_text
        original_search = config_api.search_catalog
        config_api.choose_search_query = lambda messages: (_ for _ in ()).throw(AssertionError("fast mode should not plan with model"))
        config_api.search_catalog = lambda request, query, limit=3: [fake_recommendation]

        def fake_iter_chat_text(messages, recommendations):
            captured["recommendations"] = recommendations
            yield "短剧容易让人上头，是因为节奏密、情绪反馈快。"

        config_api.iter_chat_text = fake_iter_chat_text
        try:
            response = self.client.post(
                "/api/ai/chat",
                {"mode": "fast", "messages": [{"role": "user", "content": "短剧为什么容易让人上头"}]},
                format="json",
            )
            body = b"".join(response.streaming_content).decode("utf-8")
        finally:
            config_api.choose_search_query = original_choose
            config_api.iter_chat_text = original_iter
            config_api.search_catalog = original_search

        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["recommendations"], [fake_recommendation])
        self.assertIn('"plannedByModel": false', body)
        self.assertIn("event: tool_call_start", body)
        self.assertNotIn("event: recommendations", body)

    @override_settings(AI_CHAT_API_KEY="", AI_CHAT_MODEL="", AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_ai_chat_does_not_search_for_general_conversation(self) -> None:
        response = self.client.post(
            "/api/ai/chat",
            {"messages": [{"role": "user", "content": "短剧为什么容易让人上头"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertNotIn("event: tool_call_start", body)
        self.assertNotIn("event: recommendations", body)
        self.assertIn("event: text_delta", body)
        self.assertIn("event: message_end", body)

    @override_settings(AI_EMBEDDING_API_KEY="", AI_EMBEDDING_MODEL="")
    def test_ai_search_endpoint_uses_catalog_search_shape(self) -> None:
        response = self.client.post("/api/ai/search", {"query": "神秘高手"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
        self.assertTrue(response.data["results"])
        self.assertEqual(response.data["results"][0]["type"], "episode")
        self.assertIn("snippet", response.data["results"][0])
        self.assertNotIn("关键词匹配", response.data["results"][0]["snippet"])
        self.assertIn("poster", response.data["results"][0])


class BuildSearchDocumentsCommandTests(TestCase):
    def test_builds_rich_documents_from_delivery_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = f"{tmp}/delivery.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "demo/episode_summaries.json",
                    json.dumps(
                        {
                            "drama_id": "demo",
                            "drama_title": "测试富语料剧",
                            "total_episodes": 1,
                            "episodes": [
                                {
                                    "episode_num": 1,
                                    "summary": "女主被继母陷害后决定复仇。",
                                    "mood": "压抑后反转爽感",
                                    "cliffhanger": "女主亮出关键证据。",
                                    "key_events": ["继母设局陷害女主"],
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                )
                archive.writestr(
                    "demo/characters_index.json",
                    json.dumps(
                        {
                            "characters": [
                                {"id": "c1", "name": "女主", "aliases": ["大小姐"], "description": "隐忍复仇的核心人物", "status": "active"},
                                {"id": "c2", "name": "继母", "aliases": [], "description": "幕后设局者", "status": "active"},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                )
                archive.writestr(
                    "demo/understanding_report.json",
                    json.dumps(
                        {
                            "drama_title": "测试富语料剧",
                            "characters": [
                                {"id": "c1", "name": "女主", "description": "隐忍复仇的核心人物", "status": "active"},
                                {"id": "c2", "name": "继母", "description": "幕后设局者", "status": "active"},
                            ],
                            "relationships": [{"character_a": "c1", "character_b": "c2", "relation": "表面母女，实际互相对抗"}],
                            "plot_events": [
                                {
                                    "episode_num": 1,
                                    "start_time": "00:10",
                                    "end_time": "00:30",
                                    "event_type": "reversal",
                                    "description": "女主拿出证据反击继母",
                                    "characters": ["c1", "c2"],
                                    "importance": 0.9,
                                }
                            ],
                            "plot_threads": [{"title": "复仇主线", "description": "女主查清真相并反击", "status": "open", "opened_at": 1}],
                            "episode_summaries": [],
                            "results": [],
                        },
                        ensure_ascii=False,
                    ),
                )
                archive.writestr(
                    "demo/ep_001.understanding.json",
                    json.dumps(
                        {
                            "episode_num": 1,
                            "episode_summary": "女主被继母陷害后决定复仇。",
                            "characters_mentioned": ["女主", "继母"],
                            "candidate_interactions": [{"emotion_type": "satisfying", "anchor_line": "真相就在这里", "reason": "反击爆点"}],
                        },
                        ensure_ascii=False,
                    ),
                )
                archive.writestr(
                    "demo/ep_001.interactions.json",
                    json.dumps(
                        {
                            "duration_ms": 1000,
                            "interaction_points": [
                                {
                                    "title": "女主亮证据",
                                    "component": "clue_judge_card",
                                    "emotion": "insight",
                                    "key_line": "真相就在这里",
                                    "highlight_reason": "关键反转",
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                )

            out = StringIO()
            call_command("build_search_documents", "--source", zip_path, "--all", stdout=out)

        drama_doc = SearchDocument.objects.get(object_type=SearchDocument.ObjectType.DRAMA)
        episode_doc = SearchDocument.objects.get(object_type=SearchDocument.ObjectType.EPISODE)
        self.assertIn("【主要角色】", drama_doc.body)
        self.assertIn("表面母女，实际互相对抗", drama_doc.body)
        self.assertIn("【关键事件】", episode_doc.body)
        self.assertIn("女主拿出证据反击继母", episode_doc.body)
        self.assertIn("女主亮证据", episode_doc.body)
        self.assertIn("女主", episode_doc.tags)
        self.assertEqual(episode_doc.embedding_status, "pending")

    def test_publish_existing_ready_drama_sets_published_at(self) -> None:
        drama = Drama.objects.create(slug="demo", title="旧标题", status=Drama.Status.READY)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = f"{tmp}/delivery.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr(
                    "demo/episode_summaries.json",
                    json.dumps(
                        {
                            "drama_id": "demo",
                            "drama_title": "测试发布剧",
                            "total_episodes": 1,
                            "episodes": [{"episode_num": 1, "summary": "第一集简介。"}],
                        },
                        ensure_ascii=False,
                    ),
                )
            call_command("build_search_documents", "--source", zip_path, "--drama-slug", "demo", stdout=StringIO())

        drama.refresh_from_db()
        self.assertEqual(drama.status, Drama.Status.PUBLISHED)
        self.assertIsNotNone(drama.published_at)
