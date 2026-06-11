from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from drama_agent.memory.embeddings import EmbeddingClient
from drama_agent.memory.schemas import Character


@dataclass(slots=True)
class VectorSearchResult:
    id: str
    score: float
    payload: dict[str, Any]


class VectorStore:
    """Small Qdrant wrapper with a no-op fallback for tests and offline runs."""

    def __init__(
        self,
        *,
        project_id: str,
        qdrant_path: Path | None = None,
        host: str | None = None,
        port: int | None = None,
        embed_endpoint: str = "http://localhost:11434",
        embed_model: str = "qwen3-embedding:0.6b",
        vector_size: int = 768,
        enabled: bool = True,
    ):
        self.project_id = project_id
        self.vector_size = vector_size
        self.enabled = enabled
        self._client = None
        self.embedder = EmbeddingClient(
            endpoint=embed_endpoint,
            model=embed_model,
            vector_size=vector_size,
        )
        self.collections = {
            "characters": f"{project_id}_characters",
            "events": f"{project_id}_events",
            "episode_contexts": f"{project_id}_episode_contexts",
        }
        if not enabled:
            return
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.http.models import Distance, VectorParams

            self._models = __import__("qdrant_client.http.models", fromlist=[""])
            if qdrant_path:
                qdrant_path.mkdir(parents=True, exist_ok=True)
                self._client = QdrantClient(path=str(qdrant_path))
            else:
                self._client = QdrantClient(host=host or "localhost", port=port or 6333)
            for collection in self.collections.values():
                if not self._client.collection_exists(collection):
                    self._client.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                    )
        except Exception:
            self.enabled = False
            self._client = None

    def sync_character(self, character: Character) -> None:
        text = character_vector_text(character)
        payload = {
            "id": character.id,
            "name": character.name,
            "aliases": character.aliases,
            "description": character.description,
            "status": character.status,
        }
        self.upsert_point(
            "characters",
            point_uuid(character.id),
            self.embedder.embed(text),
            payload,
        )

    def search_characters(self, text: str, *, limit: int = 5) -> list[VectorSearchResult]:
        return self.search("characters", self.embedder.embed(text), limit=limit)

    def upsert_point(
        self,
        collection: str,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        if not self.enabled or self._client is None:
            return
        models = self._models
        self._client.upsert(
            collection_name=self.collections[collection],
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )

    def delete_point(self, collection: str, point_id: str) -> None:
        if not self.enabled or self._client is None:
            return
        self._client.delete(
            collection_name=self.collections[collection],
            points_selector=[point_uuid(point_id)],
        )

    def search(
        self,
        collection: str,
        vector: list[float],
        *,
        limit: int = 5,
    ) -> list[VectorSearchResult]:
        if not self.enabled or self._client is None:
            return []
        if hasattr(self._client, "search"):
            hits = self._client.search(
                collection_name=self.collections[collection],
                query_vector=vector,
                limit=limit,
            )
        else:
            response = self._client.query_points(
                collection_name=self.collections[collection],
                query=vector,
                limit=limit,
            )
            hits = response.points
        return [
            VectorSearchResult(id=str(hit.id), score=float(hit.score), payload=dict(hit.payload or {}))
            for hit in hits
        ]

    def close(self) -> None:
        if self._client is not None and hasattr(self._client, "close"):
            self._client.close()


def point_uuid(value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"drama-agent:{value}"))


def character_vector_text(character: Character) -> str:
    aliases = " ".join(character.aliases)
    return f"{character.name} {aliases} {character.description} {character.status}".strip()
