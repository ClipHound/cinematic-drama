from __future__ import annotations

from typing import Any


def api_base_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    for suffix in ("/chat/completions", "/responses", "/files"):
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    return endpoint


def chat_completions_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return f"{api_base_url(endpoint)}/chat/completions"


def responses_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/responses"):
        return endpoint
    return f"{api_base_url(endpoint)}/responses"


def files_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/files"):
        return endpoint
    return f"{api_base_url(endpoint)}/files"


def file_url(endpoint: str, file_id: str) -> str:
    return f"{files_url(endpoint)}/{file_id}"


def extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    texts: list[str] = []
    for item in data.get("output", []):
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            texts.append(item["text"])
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if texts:
        return "".join(texts)
    for choice in data.get("choices", []):
        message = choice.get("message", {}) if isinstance(choice, dict) else {}
        if isinstance(message.get("content"), str):
            return message["content"]
    raise RuntimeError(f"Could not extract response text: {data}")
