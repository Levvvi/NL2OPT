from __future__ import annotations

import json

import pytest


class FakeMessage:
    content = '{"ok": true}'


class FakeChoice:
    message = FakeMessage()


class FakeUsage:
    def model_dump(self):
        return {"prompt_tokens": 3, "completion_tokens": 4}


class FakeResponse:
    choices = [FakeChoice()]
    usage = FakeUsage()

    def model_dump(self):
        return {"id": "fake-response", "choices": [{"message": {"content": '{"ok": true}'}}]}


class FakeCompletions:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return FakeResponse()


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeOpenAIClient:
    def __init__(self):
        self.chat = FakeChat()


def test_deepseek_client_reads_env_without_calling_api(monkeypatch):
    from nl2opt.agents.llm_client import DeepSeekClient

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.deepseek.local")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    client = DeepSeekClient()

    assert client.api_key == "test-key"
    assert client.base_url == "https://example.deepseek.local"
    assert client.model == "deepseek-v4-pro"


def test_deepseek_client_missing_api_key_error(monkeypatch):
    from nl2opt.agents.llm_client import DeepSeekClient

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        DeepSeekClient()


def test_deepseek_client_builds_expected_defaults(monkeypatch):
    from nl2opt.agents.llm_client import DeepSeekClient

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    client = DeepSeekClient()

    assert client.base_url == "https://api.deepseek.com"
    assert client.model == "deepseek-v4-flash"


def test_deepseek_client_complete_json_uses_json_object_response_format(monkeypatch):
    from nl2opt.agents.llm_client import DeepSeekClient

    fake_client = FakeOpenAIClient()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    client = DeepSeekClient(openai_client=fake_client)
    response = client.complete_json("system json", "user json", temperature=0.2)

    kwargs = fake_client.chat.completions.kwargs
    assert kwargs["model"] == "deepseek-v4-flash"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["temperature"] == 0.2
    assert kwargs["stream"] is False
    assert kwargs["messages"] == [
        {"role": "system", "content": "system json"},
        {"role": "user", "content": "user json"},
    ]
    assert json.loads(response.content) == {"ok": True}
    assert response.provider == "deepseek"
    assert response.model == "deepseek-v4-flash"
    assert response.usage == {"prompt_tokens": 3, "completion_tokens": 4}


def test_deepseek_client_reads_env_local_when_process_env_missing(monkeypatch, tmp_path):
    from nl2opt.agents.llm_client import DeepSeekClient

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text("DEEPSEEK_API_KEY=local-key\n", encoding="utf-8")

    client = DeepSeekClient(project_root=tmp_path)

    assert client.api_key == "local-key"
