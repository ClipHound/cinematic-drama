from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from django.conf import settings
from django.db.models import Q

from apps.catalog.models import Drama, Episode
from apps.search.models import SearchDocument


class AiProviderError(RuntimeError):
    pass


def _post_json(url: str, api_key: str, payload: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = request.Request(url, data=data, headers=headers, method="POST")
    max_attempts = max(1, settings.AI_HTTP_MAX_RETRIES + 1)
    for attempt in range(max_attempts):
        try:
            with request.urlopen(req, timeout=timeout or settings.AI_HTTP_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= max_attempts - 1:
                raise AiProviderError(f"AI provider returned {exc.code}: {body[:240]}") from exc
        except Exception as exc:
            if attempt >= max_attempts - 1:
                raise AiProviderError(f"AI provider request failed: {exc}") from exc
        delay = settings.AI_HTTP_RETRY_BASE_SECONDS * (2**attempt)
        if delay > 0:
            time.sleep(delay)
    raise AiProviderError("AI provider request failed")


def document_text(document: SearchDocument) -> str:
    tags = " ".join(str(tag) for tag in (document.tags or []))
    return "\n".join(part for part in [document.title, document.body, tags] if part).strip()


def embed_text(text: str) -> list[float]:
    if not settings.AI_EMBEDDING_API_KEY or not settings.AI_EMBEDDING_MODEL:
        raise AiProviderError("Embedding API is not configured")
    payload = {"model": settings.AI_EMBEDDING_MODEL, "input": text}
    if settings.AI_EMBEDDING_DIMENSIONS > 0:
        payload["dimensions"] = settings.AI_EMBEDDING_DIMENSIONS
    response = _post_json(f"{settings.AI_EMBEDDING_BASE_URL}/embeddings", settings.AI_EMBEDDING_API_KEY, payload)
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise AiProviderError("Embedding response missing data")
    embedding = data[0].get("embedding") if isinstance(data[0], dict) else None
    if not isinstance(embedding, list):
        raise AiProviderError("Embedding response missing vector")
    return [float(value) for value in embedding]


def build_embedding_for_document(document: SearchDocument) -> None:
    text = document_text(document)
    if not text:
        document.embedding_status = "failed"
        document.embedding_vector = []
        document.save(update_fields=["embedding_status", "embedding_vector", "updated_at"])
        return
    try:
        document.embedding_vector = embed_text(text)
        document.embedding_status = "ready"
    except AiProviderError:
        document.embedding_vector = []
        document.embedding_status = "failed"
        raise
    finally:
        document.save(update_fields=["embedding_status", "embedding_vector", "updated_at"])


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass(frozen=True)
class CatalogResult:
    type: str
    id: str
    drama_id: str
    title: str
    subtitle: str
    reason: str
    image_url: str
    href: str
    score: float = 0.0
    episode_number: int | None = None


def _search_result_image(request_obj, drama: Drama, episode: Episode | None = None) -> str:
    from config.api import search_result_image

    return search_result_image(request_obj, drama, episode)


def _episode_result(request_obj, episode: Episode, reason: str, score: float = 0.0) -> CatalogResult:
    return CatalogResult(
        type="episode",
        id=f"episode:{episode.id}",
        drama_id=episode.drama.slug,
        episode_number=episode.episode_number,
        title=f"{episode.drama.title} · {episode.title}",
        subtitle=episode.drama.subtitle,
        reason=reason,
        image_url=_search_result_image(request_obj, episode.drama, episode),
        href=f"/player?drama={episode.drama.slug}&episode={episode.episode_number}",
        score=score,
    )


def _drama_result(request_obj, drama: Drama, reason: str, score: float = 0.0) -> CatalogResult:
    return CatalogResult(
        type="drama",
        id=f"drama:{drama.id}",
        drama_id=drama.slug,
        title=drama.title,
        subtitle=drama.subtitle,
        reason=reason,
        image_url=_search_result_image(request_obj, drama),
        href=f"/detail?drama={drama.slug}",
        score=score,
    )


def _result_from_document(request_obj, document: SearchDocument, reason: str, score: float = 0.0) -> CatalogResult | None:
    if document.object_type == SearchDocument.ObjectType.DRAMA:
        drama = Drama.objects.filter(pk=document.object_id, status=Drama.Status.PUBLISHED).first()
        return _drama_result(request_obj, drama, reason, score) if drama else None
    if document.object_type == SearchDocument.ObjectType.EPISODE:
        episode = (
            Episode.objects.select_related("drama")
            .filter(pk=document.object_id, is_published=True, drama__status=Drama.Status.PUBLISHED)
            .first()
        )
        return _episode_result(request_obj, episode, reason, score) if episode else None
    return None


def _keyword_terms(query: str) -> list[str]:
    raw_parts = [part for part in re.split(r"[\s,，。；;、|/]+", query.casefold()) if part]
    terms: list[str] = []
    for part in raw_parts or [query.casefold()]:
        terms.append(part)
        if len(part) >= 4 and re.search(r"[\u4e00-\u9fff]", part):
            terms.extend(part[index : index + 2] for index in range(0, len(part) - 1))
    result: list[str] = []
    seen: set[str] = set()
    for term in terms:
        term = term.strip()
        if len(term) < 2 or term in seen:
            continue
        result.append(term)
        seen.add(term)
        if len(result) >= 16:
            break
    return result


def _keyword_score(document: SearchDocument, terms: list[str], query: str) -> int:
    title = document.title.casefold()
    text = document_text(document).casefold()
    score = 0
    for term in terms:
        score += min(title.count(term), 3) * 4
        score += min(text.count(term), 8)
    if query.casefold() in text:
        score += 6
    if len(terms) >= 2 and document.object_type == SearchDocument.ObjectType.DRAMA:
        score = int(score * 0.6)
    return score


def _keyword_results(request_obj, query: str, limit: int) -> list[CatalogResult]:
    terms = _keyword_terms(query)
    document_filter = Q()
    for term in terms:
        document_filter |= Q(title__icontains=term) | Q(body__icontains=term) | Q(tags__icontains=term)
    documents = list(SearchDocument.objects.filter(document_filter)[: max(limit * 8, 40)]) if document_filter else []

    ranked_documents: list[tuple[int, SearchDocument]] = []
    for document in documents:
        score = _keyword_score(document, terms, query)
        if score > 0:
            ranked_documents.append((score, document))
    ranked_documents.sort(key=lambda item: item[0], reverse=True)

    results: list[CatalogResult] = []
    for score, document in ranked_documents:
        result = _result_from_document(request_obj, document, f"关键词匹配 {score}")
        if result:
            results.append(result)
        if len(results) >= limit:
            break
    if results:
        return results[:limit]

    dramas = list(
        Drama.objects.filter(status=Drama.Status.PUBLISHED)
        .filter(
            Q(slug__icontains=query)
            | Q(title__icontains=query)
            | Q(subtitle__icontains=query)
            | Q(description__icontains=query)
            | Q(slug__icontains=terms[0] if terms else query)
            | Q(title__icontains=terms[0] if terms else query)
            | Q(subtitle__icontains=terms[0] if terms else query)
            | Q(description__icontains=terms[0] if terms else query)
        )
        .prefetch_related("episodes")[:limit]
    )
    query_text = query.casefold()
    seen = {drama.id for drama in dramas}
    for drama in Drama.objects.filter(status=Drama.Status.PUBLISHED).prefetch_related("episodes"):
        if len(dramas) >= limit:
            break
        if drama.id in seen:
            continue
        genre_text = " ".join(str(tag) for tag in (drama.genre_tags or [])).casefold()
        if query_text in genre_text:
            dramas.append(drama)
            seen.add(drama.id)
    return [_drama_result(request_obj, drama, "题材或剧目信息匹配") for drama in dramas[:limit]]


def _hybrid_score(query_vector: list[float], document: SearchDocument, terms: list[str], query: str) -> float:
    score = cosine_similarity(query_vector, [float(value) for value in document.embedding_vector])
    score += min(_keyword_score(document, terms, query), 12) * 0.015
    if len(terms) >= 2:
        if document.object_type == SearchDocument.ObjectType.EPISODE:
            score += 0.03
        elif document.object_type == SearchDocument.ObjectType.DRAMA:
            score -= 0.03
    return score


def search_catalog(request_obj, query: str, *, limit: int = 6) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    terms = _keyword_terms(query)
    ready_documents = list(SearchDocument.objects.exclude(embedding_vector=[]).filter(embedding_status="ready"))
    ranked: list[tuple[float, SearchDocument]] = []
    if ready_documents:
        try:
            query_vector = embed_text(query)
            ranked = sorted(
                ((_hybrid_score(query_vector, doc, terms, query), doc) for doc in ready_documents),
                key=lambda item: item[0],
                reverse=True,
            )
        except AiProviderError:
            ranked = []

    results: list[CatalogResult] = []
    seen_keys: set[str] = set()
    for score, document in ranked[: max(limit * 2, 10)]:
        if score <= 0:
            continue
        result = _result_from_document(request_obj, document, f"综合相似度 {score:.2f}", score)
        if not result or result.id in seen_keys:
            continue
        results.append(result)
        seen_keys.add(result.id)
        if len(results) >= limit:
            break

    if len(results) < limit:
        for result in _keyword_results(request_obj, query, limit):
            if result.id in seen_keys:
                continue
            results.append(result)
            seen_keys.add(result.id)
            if len(results) >= limit:
                break

    return [
        {
            "type": item.type,
            "id": item.id,
            "dramaId": item.drama_id,
            "episodeNumber": item.episode_number,
            "title": item.title,
            "subtitle": item.subtitle,
            "reason": item.reason,
            "imageUrl": item.image_url,
            "href": item.href,
            "score": item.score,
        }
        for item in results
    ]


_TECHNICAL_REASON_RE = re.compile(r"(相似度|综合相似度|关键词匹配|评分|分数|score|embedding|向量|检索)", re.IGNORECASE)


def _public_reason(item: dict[str, Any]) -> str:
    reason = str(item.get("reason") or "").strip()
    if reason and not _TECHNICAL_REASON_RE.search(reason):
        return reason
    if item.get("type") == "episode":
        return "这集的剧情节奏和看点更贴近你的需求。"
    return "题材、人设和剧情方向更贴近你的需求。"


def public_recommendation_item(item: dict[str, Any]) -> dict[str, Any]:
    public = {
        "type": item.get("type"),
        "id": item.get("id"),
        "dramaId": item.get("dramaId"),
        "episodeNumber": item.get("episodeNumber"),
        "title": item.get("title"),
        "subtitle": item.get("subtitle"),
        "reason": _public_reason(item),
        "imageUrl": item.get("imageUrl"),
        "href": item.get("href"),
    }
    return public


def public_recommendations(items: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    selected = items[:limit] if limit is not None else items
    return [public_recommendation_item(item) for item in selected]


def _normalize_recommendation_text(value: str) -> str:
    return re.sub(r"[\s《》\"'“”‘’·・\-—_，。！？、：:；;（）()【】\[\]]+", "", value.casefold())


def reply_uses_recommendations(reply_text: str, recommendations: list[dict[str, Any]]) -> bool:
    normalized_reply = _normalize_recommendation_text(reply_text)
    if not normalized_reply:
        return False
    for item in recommendations:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        candidates = [title]
        for separator in ("·", "路", " - ", "-", "：", ":"):
            if separator in title:
                candidates.append(title.split(separator, 1)[0].strip())
                break
        episode_number = item.get("episodeNumber")
        if episode_number and candidates[-1]:
            candidates.append(f"{candidates[-1]}第{episode_number}集")
        for candidate in candidates:
            normalized_candidate = _normalize_recommendation_text(candidate)
            if len(normalized_candidate) >= 2 and normalized_candidate in normalized_reply:
                return True
    return False


def sanitize_chat_reply(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    cleaned = re.sub(r"[（(][^）)]*(?:相似度|综合相似度|关键词匹配|评分|分数|score)[^）)]*[）)]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:相似度|综合相似度|关键词匹配|评分|分数|score)\s*[:：]?\s*\d+(?:\.\d+)?%?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:根据|基于)(?:剧库|系统)?(?:检索|搜索)(?:结果|内容|候选|命中)?[，,、：:]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:剧库|系统)(?:检索|搜索)(?:结果|内容|候选|命中)?[，,、：:]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:检索|搜索)(?:结果|内容|候选|命中)[，,、：:]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:工具调用|算法|RAG|embedding|向量)[^。！!？?\n]*[。！!？?]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([，。！？；：])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return "\n".join(line.rstrip() for line in cleaned.splitlines() if line.strip()).strip()


def _internal_score(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def build_chat_payload(messages: list[dict[str, str]], recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    context_lines = []
    for index, item in enumerate(recommendations[:3], start=1):
        content_type = "剧集" if item.get("type") == "episode" else "剧目"
        episode = f"第 {item.get('episodeNumber')} 集；" if item.get("episodeNumber") else ""
        context_lines.append(
            (
                f"{index}. 类型：{content_type}；标题：{item.get('title') or ''}；{episode}"
                f"简介：{item.get('subtitle') or ''}；播放入口：{item.get('href') or ''}；"
                f"内部匹配信号：score={_internal_score(item.get('score'))}。"
            )
        )
    context = "\n".join(context_lines)
    system = (
        "你是剧场 AI 助手，可以正常聊天、解释问题，也可以根据剧库检索结果推荐短剧。"
        "如果本轮没有提供检索结果，直接根据对话回答，不要声称已经搜索剧库，也不要编造本平台存在的剧目、链接或播放信息。"
        "如果提供了候选内容，先判断用户当前是否真的在找剧、要推荐、要播放入口或询问平台内容。"
        "如果用户只是开放聊天、观点讨论、知识解释或创作请求，忽略候选内容并正常回答，不要提及候选内容。"
        "只有需要推荐时才使用候选内容；推荐内容必须来自候选内容，推荐 1-3 个即可，用自然中文说明剧名、集数和看点。"
        "内部匹配信号只用于你排序和判断，严禁在回复中出现相似度、综合相似度、评分、score、分数、关键词匹配、检索结果、根据剧库检索、工具调用、算法、向量、embedding、RAG 等技术或系统过程描述。"
        "开头直接给推荐，不要使用“根据你的需求/兴趣、为您推荐以下内容”这类铺垫。"
        "不要逐条展示内部信号，不要解释你如何找到内容。"
    )
    user_messages = [{"role": item.get("role", "user"), "content": item.get("content", "")} for item in messages if item.get("content")]
    if context:
        user_messages.append({"role": "system", "content": f"候选内容（仅供内部推荐判断，禁止向用户暴露内部匹配信号）：\n{context}"})
    return {
        "model": settings.AI_CHAT_MODEL,
        "stream": True,
        "messages": [{"role": "system", "content": system}, *user_messages],
    }


SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_catalog",
        "description": "Search the drama catalog and return playable drama or episode recommendations.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Concise Chinese search query for drama title, genre, plot point, emotion, or interaction style.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}


def fallback_search_query(messages: list[dict[str, str]]) -> str | None:
    fallback = next((item["content"] for item in reversed(messages) if item.get("role") == "user" and item.get("content")), "")
    normalized = fallback.casefold()
    search_signals = (
        "推荐", "找", "找剧", "找一部", "找一个", "找一下", "想看", "要看", "有没有剧",
        "哪部剧", "什么剧", "搜一下", "搜索", "检索", "来点", "给我找",
    )
    if any(signal in normalized for signal in search_signals):
        return fallback
    availability_terms = ("有没有", "有吗", "能不能看", "能播放")
    content_terms = ("剧", "短剧", "剧集", "片段", "播放", "古装", "权谋", "甜宠", "复仇", "高燃")
    if any(term in normalized for term in availability_terms) and any(term in normalized for term in content_terms):
        return fallback
    return None


def choose_search_query(messages: list[dict[str, str]]) -> tuple[str | None, bool, str]:
    if not settings.AI_CHAT_API_KEY or not settings.AI_CHAT_MODEL:
        return fallback_search_query(messages), False, ""

    payload = {
        "model": settings.AI_CHAT_MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是剧场 AI 的工具路由器。仅当用户需要查询本平台剧库时调用 search_catalog，"
                    "例如找剧、推荐剧目或片段、询问平台是否有某类内容、希望进入播放。"
                    "普通寒暄、知识问答、观点讨论、创作请求、对既有回答的解释或其他无需剧库数据的问题都不要调用工具。"
                    "不调用工具时，直接完整回答用户当前的问题。"
                    "调用时把当前需求结合必要的对话上下文改写成简短中文检索词。"
                ),
            },
            *[{"role": item.get("role", "user"), "content": item.get("content", "")} for item in messages if item.get("content")],
        ],
        "tools": [SEARCH_TOOL_SCHEMA],
        "tool_choice": "auto",
    }
    response = _post_json(f"{settings.AI_CHAT_BASE_URL}/chat/completions", settings.AI_CHAT_API_KEY, payload)
    choices = response.get("choices") or []
    if not choices:
        return None, True, ""
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls") or []
    for call in tool_calls:
        function = call.get("function") if isinstance(call, dict) else None
        if not isinstance(function, dict) or function.get("name") != "search_catalog":
            continue
        try:
            args = json.loads(str(function.get("arguments") or "{}"))
        except json.JSONDecodeError:
            args = {}
        query = str(args.get("query") or "").strip()
        if query:
            return query, True, ""
    return None, True, str(message.get("content") or "").strip()


def iter_chat_text(messages: list[dict[str, str]], recommendations: list[dict[str, Any]]):
    if not settings.AI_CHAT_API_KEY or not settings.AI_CHAT_MODEL:
        if recommendations:
            titles = "、".join(str(item.get("title") or "").strip() for item in recommendations[:3] if item.get("title"))
            fallback = f"可以先看 {titles}。它们的题材和剧情节奏更贴近你的需求。" if titles else "可以先看下面这些推荐，题材和剧情节奏更贴近你的需求。"
        else:
            fallback = "当前未配置 AI 对话模型。你可以让我推荐短剧，或换个题材、角色关系和剧情点检索。"
        yield fallback
        return

    payload = build_chat_payload(messages, recommendations)
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.AI_CHAT_API_KEY}"}
    req = request.Request(
        f"{settings.AI_CHAT_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=settings.AI_HTTP_TIMEOUT_SECONDS) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield str(content)
    except Exception as exc:
        raise AiProviderError(f"Chat provider request failed: {exc}") from exc
