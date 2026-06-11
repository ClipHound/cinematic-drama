from __future__ import annotations

import hashlib
import math

import httpx


class EmbeddingClient:
    def __init__(
        self,
        *,
        endpoint: str = "http://localhost:11434",
        model: str = "qwen3-embedding:0.6b",
        vector_size: int = 768,
        timeout_sec: float = 10.0,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.vector_size = vector_size
        self.timeout_sec = timeout_sec
        self._remote_failed = False

    def embed(self, text: str) -> list[float]:
        if self.endpoint and not self._remote_failed:
            try:
                return self._embed_remote(text)
            except Exception:
                self._remote_failed = True
        return stable_embedding(text, self.vector_size)

    def _embed_remote(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": [text]}
        response = httpx.post(
            f"{self.endpoint}/embeddings",
            json=payload,
            timeout=httpx.Timeout(self.timeout_sec, connect=3.0),
        )
        response.raise_for_status()
        data = response.json()
        vector = data.get("data", [{}])[0].get("embedding")
        if not isinstance(vector, list) or not vector:
            raise RuntimeError(f"Invalid embedding response: {data}")
        if len(vector) == self.vector_size:
            return [float(value) for value in vector]
        return resize_vector([float(value) for value in vector], self.vector_size)


def stable_embedding(text: str, vector_size: int = 768) -> list[float]:
    vector = [0.0] * vector_size
    tokens = _tokens(text)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % vector_size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def resize_vector(vector: list[float], vector_size: int) -> list[float]:
    resized = [0.0] * vector_size
    for index, value in enumerate(vector):
        resized[index % vector_size] += value
    norm = math.sqrt(sum(value * value for value in resized)) or 1.0
    return [value / norm for value in resized]


def _tokens(text: str) -> list[str]:
    compact = "".join(text.split())
    if not compact:
        return ["empty"]
    chars = list(compact)
    bigrams = [compact[i : i + 2] for i in range(max(len(compact) - 1, 0))]
    return chars + bigrams
