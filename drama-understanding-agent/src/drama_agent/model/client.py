from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path
from typing import Any

import httpx

from drama_agent.model.ark_utils import (
    chat_completions_url,
    extract_response_text,
    file_url,
    files_url,
    responses_url,
)


BASE64_VIDEO_LIMIT_BYTES = 50 * 1024 * 1024


class DoubaoClient:
    """OpenAI-compatible client for Doubao Seed video understanding."""

    def __init__(
        self,
        endpoint: str,
        token: str,
        model: str,
        *,
        timeout: float = 180.0,
        max_tokens: int = 8192,
        temperature: float = 0.3,
        video_fps: float = 0.3,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.token = token
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.video_fps = video_fps

    def understand_episode(
        self,
        video_path: Path,
        episode_prompt: str,
        system_prompt: str,
    ) -> str:
        if video_path.stat().st_size > BASE64_VIDEO_LIMIT_BYTES:
            return self._understand_episode_via_file(video_path, episode_prompt, system_prompt)
        video_data = base64.b64encode(video_path.read_bytes()).decode("ascii")
        return self._chat(
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": f"data:video/mp4;base64,{video_data}"},
                        },
                        {"type": "text", "text": episode_prompt},
                    ],
                },
            ]
        )

    def analyze_frame(self, image_path: Path, prompt: str) -> str:
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return self._chat(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
        )

    def _chat(self, messages: list[dict[str, Any]]) -> str:
        if not self.token:
            raise ValueError("DRAMA_AGENT_MODEL_TOKEN or AI_VLM_TOKEN is required for model calls")
        if not self.model:
            raise ValueError("DRAMA_AGENT_MODEL_NAME or AI_VLM_MODEL is required for model calls")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        attempts = 0
        while True:
            attempts += 1
            try:
                with httpx.Client(timeout=self.timeout if attempts == 1 else self.timeout * 2) as client:
                    response = client.post(
                        chat_completions_url(self.endpoint),
                        headers={"Authorization": f"Bearer {self.token}"},
                        json=payload,
                    )
                if response.status_code == 429 and attempts < 3:
                    time.sleep(60)
                    continue
                if response.status_code >= 500 and attempts < 2:
                    time.sleep(30)
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException:
                if attempts < 2:
                    continue
                raise

    def _understand_episode_via_file(
        self,
        video_path: Path,
        episode_prompt: str,
        system_prompt: str,
    ) -> str:
        file_id = self._upload_video_file(video_path)
        self._wait_for_file_processed(file_id)
        payload = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_video", "file_id": file_id},
                        {"type": "input_text", "text": f"{system_prompt}\n\n{episode_prompt}"},
                    ],
                }
            ],
            "temperature": self.temperature,
            "max_output_tokens": self.max_tokens,
        }
        response = self._post_json_with_retries(responses_url(self.endpoint), payload)
        return extract_response_text(response)

    def _upload_video_file(self, video_path: Path) -> str:
        mime_type = mimetypes.guess_type(video_path.name)[0] or "video/mp4"
        with video_path.open("rb") as fh:
            files = {"file": (video_path.name, fh, mime_type)}
            data = {
                "purpose": "user_data",
                "preprocess_configs[video][fps]": str(self.video_fps),
            }
            response = httpx.post(
                files_url(self.endpoint),
                headers={"Authorization": f"Bearer {self.token}"},
                data=data,
                files=files,
                timeout=httpx.Timeout(max(self.timeout, 300.0), connect=30.0),
            )
        response.raise_for_status()
        data = response.json()
        file_id = data.get("id")
        if not file_id:
            raise RuntimeError(f"File upload response did not include id: {data}")
        return file_id

    def _wait_for_file_processed(self, file_id: str) -> None:
        deadline = time.monotonic() + max(self.timeout, 300.0)
        while True:
            response = httpx.get(
                file_url(self.endpoint, file_id),
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=httpx.Timeout(60.0, connect=15.0),
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            if status in {None, "active", "processed", "success", "succeeded", "completed"}:
                return
            if status in {"failed", "error", "cancelled"}:
                raise RuntimeError(f"File processing failed: {data}")
            if time.monotonic() > deadline:
                raise TimeoutError(f"Timed out waiting for file processing: {file_id}")
            time.sleep(2)

    def _post_json_with_retries(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = 0
        while True:
            attempts += 1
            with httpx.Client(timeout=max(self.timeout, 300.0)) as client:
                response = client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    json=payload,
                )
            if response.status_code == 429 and attempts < 3:
                time.sleep(60)
                continue
            if response.status_code >= 500 and attempts < 2:
                time.sleep(30)
                continue
            response.raise_for_status()
            return response.json()
