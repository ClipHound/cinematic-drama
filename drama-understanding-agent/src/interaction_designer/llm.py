from __future__ import annotations

from drama_agent.model.client import DoubaoClient


class TextLLM:
    def __init__(self, endpoint: str, token: str, model: str, *, timeout: float = 180.0):
        self.client = DoubaoClient(endpoint, token, model, timeout=timeout, temperature=0.2)

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        return self.client._chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
