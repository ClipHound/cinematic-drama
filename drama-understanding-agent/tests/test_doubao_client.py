from drama_agent.config import Settings
from drama_agent.model.ark_utils import (
    chat_completions_url,
    extract_response_text,
    file_url,
    files_url,
    responses_url,
)


def test_ark_urls_accept_base_or_full_paths() -> None:
    base = "https://ark.cn-beijing.volces.com/api/v3"

    assert chat_completions_url(base) == f"{base}/chat/completions"
    assert chat_completions_url(f"{base}/chat/completions") == f"{base}/chat/completions"
    assert responses_url(f"{base}/chat/completions") == f"{base}/responses"
    assert files_url(f"{base}/responses") == f"{base}/files"
    assert file_url(base, "file-123") == f"{base}/files/file-123"


def test_extract_response_text_supports_responses_and_chat_shapes() -> None:
    assert extract_response_text({"output_text": "a"}) == "a"
    assert extract_response_text({"output": [{"content": [{"text": "b"}]}]}) == "b"
    assert extract_response_text({"choices": [{"message": {"content": "c"}}]}) == "c"


def test_settings_can_reuse_server_ai_vlm_env(monkeypatch) -> None:
    monkeypatch.setenv("AI_VLM_ENDPOINT", "https://ark.cn-beijing.volces.com/api/v3")
    monkeypatch.setenv("AI_VLM_TOKEN", "token")
    monkeypatch.setenv("AI_VLM_MODEL", "ep-test")

    settings = Settings(_env_file=None)

    assert settings.model_endpoint == "https://ark.cn-beijing.volces.com/api/v3"
    assert settings.model_token == "token"
    assert settings.model_name == "ep-test"
