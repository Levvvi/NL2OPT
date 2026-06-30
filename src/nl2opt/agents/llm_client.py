from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from nl2opt.config import get_config_value, get_deepseek_api_key


class LLMResponse(BaseModel):
    content: str
    provider: str = "mock"
    model: str = "mock"
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


class LLMClient(Protocol):
    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        ...


MockPayload = dict[str, Any] | str | Callable[[str, str, float], dict[str, Any] | str | LLMResponse]


class MockLLMClient:
    def __init__(self, response: MockPayload):
        self.response = response

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        payload = self.response
        if callable(payload):
            payload = payload(system_prompt, user_prompt, temperature)
        if isinstance(payload, LLMResponse):
            return payload
        if isinstance(payload, dict):
            content = json.dumps(payload, ensure_ascii=False)
        else:
            content = str(payload)
        return LLMResponse(content=content, provider="mock", model="mock-extractor")


class DeepSeekClient:
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-v4-flash"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_sec: float = 60.0,
        max_tokens: int = 4096,
        openai_client: Any | None = None,
        project_root: Path | None = None,
    ):
        resolved_api_key = api_key or get_deepseek_api_key(project_root=project_root)
        if not resolved_api_key:
            raise ValueError("DeepSeek API key is missing. Set DEEPSEEK_API_KEY.")

        self.api_key = resolved_api_key
        self.base_url = (
            base_url
            or get_config_value("DEEPSEEK_BASE_URL", project_root=project_root)
            or self.DEFAULT_BASE_URL
        )
        self.model = (
            model
            or get_config_value("DEEPSEEK_MODEL", project_root=project_root)
            or self.DEFAULT_MODEL
        )
        self.timeout_sec = timeout_sec
        self.max_tokens = max_tokens
        self._openai_client = openai_client

    def _client(self) -> Any:
        if self._openai_client is None:
            from openai import OpenAI

            self._openai_client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout_sec,
            )
        return self._openai_client

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse:
        response = self._client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=self.max_tokens,
            stream=False,
        )

        choices = getattr(response, "choices", None) or []
        content = None
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
        if not content or not str(content).strip():
            raise ValueError("DeepSeek API returned empty content.")

        usage = getattr(response, "usage", None)
        usage_data = None
        if usage is not None:
            if hasattr(usage, "model_dump"):
                usage_data = usage.model_dump()
            elif isinstance(usage, dict):
                usage_data = usage

        raw = response.model_dump() if hasattr(response, "model_dump") else None
        return LLMResponse(
            content=str(content),
            provider="deepseek",
            model=self.model,
            usage=usage_data,
            raw=raw,
        )
