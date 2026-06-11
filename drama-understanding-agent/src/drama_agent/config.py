from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


RunMode = Literal["full_auto", "hitl_light", "hitl_strict"]


class Settings(BaseSettings):
    """Process-level settings loaded from environment or .env."""

    model_config = SettingsConfigDict(
        env_prefix="DRAMA_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    projects_root: Path = Field(default=Path("projects"))
    model_endpoint: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        validation_alias=AliasChoices("DRAMA_AGENT_MODEL_ENDPOINT", "AI_VLM_ENDPOINT"),
    )
    model_token: str = Field(
        default="",
        validation_alias=AliasChoices("DRAMA_AGENT_MODEL_TOKEN", "AI_VLM_TOKEN"),
    )
    model_name: str = Field(
        default="",
        validation_alias=AliasChoices("DRAMA_AGENT_MODEL_NAME", "AI_VLM_MODEL"),
    )
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    embed_endpoint: str = "http://localhost:11434"
    embed_model: str = "qwen3-embedding:0.6b"
    asr_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("DRAMA_AGENT_ASR_ENDPOINT", "AI_ASR_ENDPOINT"),
    )
    mode: RunMode = "full_auto"
    request_timeout_sec: float = 180.0


def load_settings() -> Settings:
    return Settings()
