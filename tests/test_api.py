from __future__ import annotations

import http.client
import json
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from nl2opt import api, api_worker
from nl2opt.agents.llm_client import LLMResponse, MockLLMClient
from nl2opt.api_contract import ApiError, check_instance_limits, envelope, production_spec


PARAMETERS = {"labor_capacity": 100, "material_capacity": 80}
PRODUCTION = {"mode": "production", "parameters": PARAMETERS}
TOKEN = "test-only-token-with-at-least-24-characters"


@contextmanager
def serving(config=None):
    server = api.Server(config or api.Config(port=0))
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(server, path="solve", data=None, headers=None, raw=None, method=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=15)
    body = raw if raw is not None else json.dumps(data) if data is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    connection.request(method or ("POST" if body is not None else "GET"), f"/api/v1/nl2opt/{path}", body, request_headers)
    response = connection.getresponse()
    result = response.status, dict(response.headers), json.loads(response.read())
    connection.close()
    return result


def test_http_real_solver_and_checker(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with serving() as server:
        status, headers, body = request(server, data=PRODUCTION)
        assert status == 200
        assert body["status"] == "succeeded"
        assert body["solver_result"]["solution"]["quantities"] == {"A": 40, "B": 20}
        assert body["solver_result"]["objective_value"] == 2200
        assert body["checker_report"]["passed"] is True
        assert body["checker_report"]["resource_usage"] == {"labor": 100, "material": 80}
        assert body["provenance"]["source"] == "live_solver"
        assert body["provenance"]["semantic_equivalence_proven"] is False
        assert headers["Cache-Control"] == "no-store"
        assert "output_dir" not in json.dumps(body)
        assert "stderr" not in json.dumps(body)
        # Changed input must execute the model rather than return the reference answer.
        status, _, changed = request(server, data={"mode": "production", "parameters": {
            "labor_capacity": 90, "material_capacity": 60}})
        assert status == 200
        assert changed["solver_result"]["solution"]["quantities"] == {"A": 40, "B": 10}
        assert changed["solver_result"]["objective_value"] == 1900
        assert changed["run_id"] != body["run_id"]


@pytest.mark.parametrize("quantities,objective,fragment", [
    ({"A": 41, "B": 20}, 2240, "capacity exceeded"),
    ({"A": 0.5, "B": 0}, 20, "integer"),
    ({"A": 40, "B": 20}, 999, "objective mismatch"),
])
def test_http_injection_uses_real_checker(quantities, objective, fragment):
    with serving() as server:
        status, _, body = request(server, "check", {
            "parameters": PARAMETERS, "quantities": quantities, "objective_value": objective})
        assert status == 422
        assert body["error"]["code"] == "CHECKER_REJECTED"
        assert body["stage"] == "checker"
        assert body["provenance"]["source"] == "injected_check"
        assert body["diagnostics"]["solver_executed"] is False
        assert any(fragment in item for item in body["checker_report"]["violations"])


def test_health_and_text_missing_key_never_fall_back(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with serving() as server:
        status, _, body = request(server, "health")
        assert status == 200
        assert body["capabilities"] == {"production": True, "check": True, "text": False}
        assert body["deepseek_configured"] is False
        status, _, body = request(server, data={"mode": "text", "text": "生产计划利润最大化"})
        assert status == 503
        assert body["error"]["code"] == "MODEL_NOT_CONFIGURED"
        assert body["solver_result"] is None


def test_text_requires_server_token_and_health_reflects_request(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "not-a-real-key-never-sent")
    with serving(api.Config(port=0, token=TOKEN)) as server:
        status, _, body = request(server, "health")
        assert status == 200 and body["capabilities"]["text"] is False
        status, _, body = request(server, "health", headers={"Authorization": f"Bearer {TOKEN}"})
        assert body["capabilities"]["text"] is True
        status, _, body = request(server, data={"mode": "text", "text": "生产计划利润最大化"})
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("data", [
    {**PRODUCTION, "code": "print('no')"},
    {"mode": "raw", "parameters": PARAMETERS},
    {"mode": "production", "parameters": {"labor_capacity": True, "material_capacity": 80}},
    {"mode": "production", "parameters": {"labor_capacity": 201, "material_capacity": 80}},
    {"mode": "production", "parameters": {"labor_capacity": 10 ** 400, "material_capacity": 80}},
    {"mode": "production", "parameters": {"labor_capacity": 1.5, "material_capacity": 80}},
    {"mode": "text", "text": "a" * 2001},
    {"mode": "text", "text": " "},
    {"mode": "text", "text": "ok", "api_key": "do-not-accept"},
    [],
])
def test_invalid_inputs_rejected_before_worker(data, monkeypatch):
    monkeypatch.setattr(api, "run_isolated", lambda *_: pytest.fail("worker must not run"))
    with serving() as server:
        status, _, body = request(server, data=data)
        assert status == 400
        assert body["stage"] == "input"


def test_nonfinite_oversized_and_unknown_history(monkeypatch):
    monkeypatch.setattr(api, "run_isolated", lambda *_: pytest.fail("worker must not run"))
    with serving() as server:
        assert request(server, raw='{"mode":"production","parameters":{"labor_capacity":NaN,"material_capacity":80}}')[0] == 400
        assert request(server, raw="x" * (16384 + 1))[0] == 413
        assert request(server, path="runs/123")[0] == 404
        assert request(server, data=PRODUCTION, headers={"Content-Type": "text/plain"})[0] == 415


def test_origin_and_host_boundary(monkeypatch):
    monkeypatch.setattr(api, "run_isolated", lambda *_: pytest.fail("worker must not run"))
    with serving(api.Config(port=0, allowed_origins=("https://portfolio.example",))) as server:
        assert request(server, data=PRODUCTION, headers={"Origin": "https://attacker.example"})[0] == 403
        assert request(server, "health", headers={"Host": "attacker.example"})[0] == 403
        status, headers, _ = request(server, "health", headers={"Origin": "https://portfolio.example"})
        assert status == 200
        assert headers["Access-Control-Allow-Origin"] == "https://portfolio.example"
        assert "Access-Control-Allow-Credentials" not in headers


def test_remote_binding_refuses_accidental_public_service():
    with pytest.raises(ValueError, match="Remote binding"):
        api.Config(host="0.0.0.0").validate()
    with pytest.raises(ValueError, match="24 characters"):
        api.Config(token="weak").validate()
    api.Config(host="0.0.0.0", public_demo=True).validate()


def test_rate_and_concurrency_reject_without_running(monkeypatch):
    monkeypatch.setattr(api, "run_isolated", lambda *_: pytest.fail("worker must not run"))
    with serving(api.Config(port=0, concurrency=1, requests_per_minute=1)) as server:
        server.workers.acquire()
        try:
            status, _, body = request(server, data=PRODUCTION)
            assert status == 503 and body["error"]["code"] == "SERVER_BUSY"
            status, _, body = request(server, data=PRODUCTION)
            assert status == 429 and body["error"]["code"] == "RATE_LIMITED"
        finally:
            server.workers.release()


def test_text_quota_and_expiry():
    limiter = api.RateLimiter(api.Config(text_per_day=1))
    assert limiter.allow("a", True, now=1)
    assert not limiter.allow("b", True, now=2)
    assert limiter.allow("b", False, now=2)
    assert limiter.allow("a", True, now=86402)


def test_whole_request_deadline_stops_isolated_worker():
    started = time.monotonic()
    status, body = api.run_isolated(replace(api.Config(), deadline_sec=0.000001), "solve", PRODUCTION,
                                    envelope("production", "live_solver"))
    assert status == 504
    assert body["error"]["code"] == "REQUEST_TIMEOUT"
    assert body["diagnostics"]["timed_out"] is True
    assert time.monotonic() - started < 5


def text_worker_request():
    return {"operation": "solve", "data": {"mode": "text", "text": "生产两种产品，利润最大化"},
            "envelope": envelope("text", "live_solver"), "solver_timeout_sec": 10, "model_timeout_sec": 1}


def test_text_mock_extraction_still_uses_real_solver(tmp_path, monkeypatch):
    mocked = api_worker.MeteredClient(MockLLMClient(production_spec(PARAMETERS).model_dump(mode="json")))
    monkeypatch.setattr(api_worker, "create_client", lambda *_: mocked)
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 200
    assert body["solver_result"]["objective_value"] == 2200
    assert body["checker_report"]["passed"] is True
    assert body["provenance"]["model"] == "mock-extractor"
    assert body["provenance"]["prompt_version"] == "v3"


def test_provider_reported_model_is_distinct_from_requested_alias(tmp_path, monkeypatch):
    response = LLMResponse(content=json.dumps(production_spec(PARAMETERS).model_dump(mode="json")),
                           model="requested-alias", raw={"model": "provider-reported-model"})
    mock = MockLLMClient(lambda *_: response)
    mock.model = "requested-alias"
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(mock))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 200
    assert body["provenance"]["requested_model"] == "requested-alias"
    assert body["provenance"]["model"] == "provider-reported-model"
    assert body["provenance"]["model_identifier_source"] == "provider_response"


@pytest.mark.parametrize("raw", [None, {}, {"model": None}, {"model": ""}, {"model": 123}])
def test_missing_reported_model_labels_request_alias_as_fallback(raw):
    response = LLMResponse(content="{}", model="requested-alias", raw=raw)
    mock = MockLLMClient(lambda *_: response)
    mock.model = "requested-alias"
    client = api_worker.MeteredClient(mock)
    client.complete_json("system", "user")
    assert client.model == "requested-alias"
    assert client.requested_model == "requested-alias"
    assert client.model_identifier_source == "requested_model"


def test_client_response_without_raw_attribute_is_supported():
    response = SimpleNamespace(content="{}", usage=None, model="test-client-model")
    client = api_worker.MeteredClient(SimpleNamespace(complete_json=lambda *_: response))
    assert client.complete_json("system", "user") is response
    assert client.model == "test-client-model"
    assert client.requested_model is None
    assert client.model_identifier_source == "client_identifier"


@pytest.mark.parametrize("mock_response,code", [
    ("not valid JSON", "INVALID_MODEL_JSON"),
    ({"problem_type": "production"}, "SCHEMA_VALIDATION_FAILED"),
])
def test_model_failure_attribution_sanitizes_raw_response(tmp_path, monkeypatch, mock_response, code):
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(MockLLMClient(mock_response)))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 422
    assert body["error"]["code"] == code
    assert body["solver_result"] is None
    assert "raw_response" not in body


def test_missing_fields_stop_before_solver(tmp_path, monkeypatch):
    data = production_spec(PARAMETERS).model_dump(mode="json")
    data["missing_fields"] = ["products.0.profit"]
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(MockLLMClient(data)))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 422
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELDS"
    assert body["diagnostics"]["solver_executed"] is False
    assert not list(tmp_path.glob("generated_model.py"))


def test_missing_run_identifier_is_generated_as_metadata(tmp_path, monkeypatch):
    data = production_spec(PARAMETERS).model_dump(mode="json")
    data["missing_fields"] = ["problem_id"]
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(MockLLMClient(data)))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 200
    assert body["problem_spec"]["problem_id"] == body["run_id"]
    assert body["problem_spec"]["missing_fields"] == []
    assert body["diagnostics"]["generated_metadata"] == {"problem_id": body["run_id"]}
    assert "generated by the API" in body["problem_spec"]["assumptions"][-1]
    assert body["solver_result"]["objective_value"] == 2200


def test_generated_metadata_cannot_clear_missing_capacity(tmp_path, monkeypatch):
    data = production_spec(PARAMETERS).model_dump(mode="json")
    data["missing_fields"] = ["problem_id", "resources.0.capacity"]
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(MockLLMClient(data)))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 422
    assert body["error"]["code"] == "MISSING_REQUIRED_FIELDS"
    assert body["problem_spec"]["missing_fields"] == ["resources.0.capacity"]
    assert body["diagnostics"]["solver_executed"] is False
    assert not list(tmp_path.glob("generated_model.py"))


def test_provider_exception_never_exposes_secrets(tmp_path, monkeypatch):
    def broken(*_args):
        raise RuntimeError("secret-key /private/config.json https://private-host")
    monkeypatch.setattr(api_worker, "create_client", lambda *_: api_worker.MeteredClient(MockLLMClient(broken)))
    status, body = api_worker.execute(text_worker_request(), tmp_path)
    assert status == 502
    assert body["error"]["code"] == "EXTRACTION_FAILED"
    assert "secret-key" not in json.dumps(body)
    assert "/private/" not in json.dumps(body)


def test_large_and_nonfinite_extracted_instances_rejected():
    data = production_spec(PARAMETERS).model_dump(mode="json")
    spec = production_spec(PARAMETERS)
    spec.products = spec.products * 6
    with pytest.raises(ApiError, match="规模"):
        check_instance_limits(spec)
    data["products"][0]["profit"] = float("inf")
    # model_construct mirrors an untrusted/buggy extractor without schema masking.
    spec = production_spec(PARAMETERS)
    spec.products[0].profit = float("inf")
    with pytest.raises(ApiError, match="有限"):
        check_instance_limits(spec)
