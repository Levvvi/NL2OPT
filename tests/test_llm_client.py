from __future__ import annotations

import json


def test_mock_llm_client_returns_dict_as_json():
    from nl2opt.agents.llm_client import MockLLMClient

    client = MockLLMClient({"problem_id": "demo", "problem_type": "production"})
    response = client.complete_json("system", "user")

    assert json.loads(response.content)["problem_id"] == "demo"
    assert response.provider == "mock"
    assert response.model == "mock-extractor"


def test_mock_llm_client_returns_string_response():
    from nl2opt.agents.llm_client import MockLLMClient

    client = MockLLMClient('{"ok": true}')
    response = client.complete_json("system", "user")

    assert response.content == '{"ok": true}'


def test_llm_response_has_provider_and_model():
    from nl2opt.agents.llm_client import LLMResponse

    response = LLMResponse(content="{}")

    assert response.provider == "mock"
    assert response.model == "mock"
