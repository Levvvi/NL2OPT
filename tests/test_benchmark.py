from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

import nl2opt.eval.benchmark as benchmark_module
from nl2opt.agents.extractor import ExtractorResult
from nl2opt.agents.llm_client import LLMResponse, MockLLMClient
from nl2opt.eval.benchmark import (
    BenchmarkAttempt,
    BenchmarkItem,
    BenchmarkRunConfig,
    call_with_transport_retry,
    judge_benchmark_result,
    load_benchmark_dataset,
    run_benchmark,
)
from nl2opt.eval.bench_report import summarize_token_usage
from nl2opt.eval.run_bench import build_parser


def _write_dataset(
    directory: Path,
    *,
    rows: list[dict[str, object]],
    dataset: str = "nl4opt",
    digest: str | None = None,
    count: int | None = None,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    local_filename = "NL4Opt_fixed.jsonl" if dataset == "nl4opt" else "IndustryOR_fixedV2.jsonl"
    upstream_filename = "NL4OPT.jsonl" if dataset == "nl4opt" else "IndustryOR_fixedV2.json"
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")
    (directory / local_filename).write_bytes(payload)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "datasets": {
                    dataset: {
                        "upstream_filename": upstream_filename,
                        "local_filename": local_filename,
                        "revision": "pinned-revision",
                        "url": "https://example.invalid/dataset",
                        "sha256": digest or hashlib.sha256(payload).hexdigest(),
                        "license": "Apache-2.0",
                        "expected_nonblank_rows": count if count is not None else len(rows),
                    }
                }
            }
        ),
        encoding="utf-8",
    )


def _rows(count: int = 1) -> list[dict[str, object]]:
    return [
        {"id": f"item-{index}", "en_question": f"maximize x subject to x <= {index + 1}", "en_answer": index + 1}
        for index in range(count)
    ]


def _count_csv_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def _successful_attempt(*_args: object, **_kwargs: object) -> BenchmarkAttempt:
    return BenchmarkAttempt(
        status="OPTIMAL",
        objective_value=1.0,
        checker_passed=True,
    )


def _fake_config(tmp_path: Path, *, resume: bool = False) -> BenchmarkRunConfig:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())
    return BenchmarkRunConfig(
        datasets_dir=datasets_dir,
        results_csv=tmp_path / "results.csv",
        dataset="nl4opt",
        track="en",
        repetitions=1,
        resume=resume,
        attempt_runner=_successful_attempt,
    )


def test_loader_rejects_manifest_hash_mismatch(tmp_path: Path) -> None:
    _write_dataset(tmp_path, rows=_rows(), digest="0" * 64)

    with pytest.raises(ValueError, match="sha256"):
        load_benchmark_dataset("nl4opt", tmp_path)


def test_loader_rejects_manifest_count_mismatch(tmp_path: Path) -> None:
    _write_dataset(tmp_path, rows=_rows(), count=2)

    with pytest.raises(ValueError, match="count"):
        load_benchmark_dataset("nl4opt", tmp_path)


def test_loader_returns_utf8_rows_with_stable_item_ids(tmp_path: Path) -> None:
    _write_dataset(tmp_path, rows=[{"en_question": "最大化 x", "en_answer": 2}])

    items = load_benchmark_dataset("nl4opt", tmp_path)

    assert len(items) == 1
    assert items[0].dataset == "nl4opt"
    assert items[0].item_id == "nl4opt-0001"
    assert items[0].question == "最大化 x"
    assert items[0].ground_truth == 2


def test_judge_returns_both_tolerances_for_numeric_answers() -> None:
    judgment = judge_benchmark_result(
        prediction={"status": "OPTIMAL", "objective_value": 10.00001},
        ground_truth=10.0,
        spec=None,
        checker_passed=True,
        tolerance=1e-6,
    )

    assert judgment.passed_1e_6 is False
    assert judgment.passed_1e_4 is True


@pytest.mark.parametrize(
    ("status", "checker_passed", "expected"),
    [
        ("INFEASIBLE", True, True),
        ("INFEASIBLE", False, False),
        ("OPTIMAL", True, False),
    ],
)
def test_judge_accepts_infeasible_only_when_checker_independently_passes(
    status: str,
    checker_passed: bool,
    expected: bool,
) -> None:
    judgment = judge_benchmark_result(
        prediction={"status": status},
        ground_truth="INFEASIBLE",
        spec=None,
        checker_passed=checker_passed,
        tolerance=1e-6,
    )

    assert judgment.passed_1e_6 is expected
    assert judgment.passed_1e_4 is expected


@pytest.mark.parametrize("ground_truth", ("No Best Solution", "-99999", -99999))
def test_judge_treats_revised_infeasible_targets_as_verified_infeasibility(ground_truth: object) -> None:
    accepted = judge_benchmark_result(
        prediction={"status": "INFEASIBLE"},
        ground_truth=ground_truth,
        spec=None,
        checker_passed=True,
        tolerance=1e-6,
    )
    rejected = judge_benchmark_result(
        prediction={"status": "OPTIMAL", "objective_value": -99999},
        ground_truth=ground_truth,
        spec=None,
        checker_passed=True,
        tolerance=1e-6,
    )

    assert accepted.passed_1e_6 is True
    assert rejected.passed_1e_6 is False


def test_vendored_answers_are_numeric_or_accepted_infeasible_targets() -> None:
    datasets_dir = Path(__file__).parents[1] / "eval" / "datasets"
    dataset_names = json.loads((datasets_dir / "manifest.json").read_text(encoding="utf-8"))["datasets"]

    for dataset_name in dataset_names:
        for item in load_benchmark_dataset(dataset_name, datasets_dir):
            try:
                expected = float(item.ground_truth)
            except (TypeError, ValueError):
                judgment = judge_benchmark_result(
                    prediction={"status": "INFEASIBLE"},
                    ground_truth=item.ground_truth,
                    spec=None,
                    checker_passed=True,
                    tolerance=1e-6,
                )
            else:
                judgment = judge_benchmark_result(
                    prediction={"status": "OPTIMAL", "objective_value": expected},
                    ground_truth=item.ground_truth,
                    spec=None,
                    checker_passed=True,
                    tolerance=1e-6,
                )

            assert judgment.passed_1e_6 is True, f"{dataset_name}/{item.item_id}"


def test_transport_retry_uses_the_pinned_backoff_schedule() -> None:
    attempts = 0
    sleeps: list[int] = []

    def flaky_call() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionError("connection reset")
        return "ok"

    assert call_with_transport_retry(flaky_call, sleep=sleeps.append) == "ok"
    assert attempts == 3
    assert sleeps == [2, 4]


def test_default_attempt_short_circuits_unsupported_route_before_extraction(tmp_path: Path, monkeypatch) -> None:
    item = BenchmarkItem("nl4opt", "unsupported-item", "irrelevant", 1, {})
    config = BenchmarkRunConfig(results_csv=tmp_path / "results.csv", dataset="nl4opt", track="en", repetitions=1)

    def extractor_must_not_run(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("extractor must not run for an unsupported router result")

    monkeypatch.setattr(benchmark_module, "extract_problem_spec", extractor_must_not_run)

    attempt = benchmark_module._run_default_attempt(
        item,
        "Please write a poem about spring.",
        1,
        config,
        MockLLMClient({}),
        tmp_path / "attempt",
    )

    assert attempt.status == "UNSUPPORTED"
    assert attempt.details["router_problem_type"] == "unsupported"
    assert attempt.details["router_reason"]


def test_runner_records_complete_failure_telemetry_and_utc_manifest_times(tmp_path: Path, monkeypatch) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())

    def response_backed_extraction(*_args: object, **_kwargs: object) -> ExtractorResult:
        return ExtractorResult(
            text="maximize x subject to x <= 1",
            problem_type="generic_lp_milp",
            success=False,
            spec=None,
            spec_dict=None,
            raw_response="{}",
            system_prompt="system",
            user_prompt="user",
            validation_errors=["invalid spec"],
            error="schema validation failed",
            provider="fake-provider",
            model="fake-extractor",
            prompt_version="v4",
        )

    monkeypatch.setattr(benchmark_module, "extract_problem_spec", response_backed_extraction)
    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            client=MockLLMClient({}),
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["failure_category"] == "EXTRACT_ERR"
    assert row["router_problem_type"] == "generic_lp_milp"
    assert row["extractor_provider"] == "fake-provider"
    assert row["extractor_model"] == "fake-extractor"
    assert float(row["wall_sec"]) >= 0
    assert row["evaluated_at"].endswith("Z")
    assert datetime.fromisoformat(row["evaluated_at"].removesuffix("Z") + "+00:00").tzinfo is not None

    artifact = json.loads(Path(row["failure_artifact"]).read_text(encoding="utf-8"))
    assert artifact["failure_category"] == "EXTRACT_ERR"
    assert artifact["router_problem_type"] == "generic_lp_milp"
    assert artifact["router_reason"]
    assert artifact["extractor_provider"] == "fake-provider"
    assert artifact["extractor_model"] == "fake-extractor"
    assert float(artifact["wall_sec"]) >= 0
    assert artifact["evaluated_at"].endswith("Z")
    assert datetime.fromisoformat(artifact["evaluated_at"].removesuffix("Z") + "+00:00").tzinfo is not None

    manifest = json.loads((results.parent / "run_manifest.json").read_text(encoding="utf-8"))
    for key in ("started_at", "completed_at"):
        assert manifest[key].endswith("Z")
        assert datetime.fromisoformat(manifest[key].removesuffix("Z") + "+00:00").tzinfo is not None


def test_runner_serializes_extractor_usage_for_response_backed_failure(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())
    usage = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            client=MockLLMClient(
                LLMResponse(
                    content="{}",
                    provider="fake-provider",
                    model="fake-extractor",
                    usage=usage,
                )
            ),
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert json.loads(row["extractor_usage"]) == usage

    artifact = json.loads(Path(row["failure_artifact"]).read_text(encoding="utf-8"))
    assert artifact["extractor_usage"] == usage


def test_summarize_token_usage_separates_translation_and_extraction_tokens() -> None:
    totals = summarize_token_usage(
        [
            {
                "translation_usage": json.dumps(
                    {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8}
                ),
                "extractor_usage": json.dumps(
                    {"prompt_tokens": 13, "completion_tokens": 17, "total_tokens": 30}
                ),
            },
            {
                "translation_usage": json.dumps({"prompt_tokens": 2, "total_tokens": 2}),
                "extractor_usage": "not-json",
            },
            {},
        ]
    )

    assert totals == {
        "translation_prompt_tokens": 5,
        "translation_completion_tokens": 5,
        "translation_total_tokens": 10,
        "extractor_prompt_tokens": 13,
        "extractor_completion_tokens": 17,
        "extractor_total_tokens": 30,
    }


@pytest.mark.parametrize(
    ("attempt", "ground_truth", "expected_category"),
    [
        (BenchmarkAttempt(status="UNSUPPORTED"), 1, "UNSUPPORTED"),
        (BenchmarkAttempt(status="API_ERROR", error="LLM client failed"), 1, "API_ERR"),
        (BenchmarkAttempt(status="EXTRACTION_ERROR", error="schema validation failed"), 1, "EXTRACT_ERR"),
        (BenchmarkAttempt(status="TIMEOUT", error="solver timed out"), 1, "SOLVE_TIMEOUT"),
        (BenchmarkAttempt(status="INFEASIBLE", checker_passed=False), "INFEASIBLE", "INFEASIBLE_MISMATCH"),
        (BenchmarkAttempt(status="OPTIMAL", objective_value=2.0, checker_passed=True), 1, "WRONG_OPT"),
        (BenchmarkAttempt(status="ERROR", error="solver process failed"), 1, "CODEGEN_ERR"),
    ],
)
def test_runner_uses_protocol_failure_categories(
    tmp_path: Path,
    attempt: BenchmarkAttempt,
    ground_truth: object,
    expected_category: str,
) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=[{"id": "one", "en_question": "maximize x subject to x <= 1", "en_answer": ground_truth}])

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            attempt_runner=lambda *_args: attempt,
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["failure_category"] == expected_category


def test_resume_does_not_duplicate_completed_attempt(tmp_path: Path) -> None:
    run_benchmark(_fake_config(tmp_path))
    run_benchmark(_fake_config(tmp_path, resume=True))

    assert _count_csv_rows(tmp_path / "results.csv") == 1


def test_resume_preserves_initial_manifest_started_at(tmp_path: Path) -> None:
    config = _fake_config(tmp_path)
    run_benchmark(config)
    manifest_path = tmp_path / "run_manifest.json"
    started_at = json.loads(manifest_path.read_text(encoding="utf-8"))["started_at"]

    run_benchmark(_fake_config(tmp_path, resume=True))

    assert json.loads(manifest_path.read_text(encoding="utf-8"))["started_at"] == started_at


def test_resume_rejects_protocol_mismatch_before_rewriting_manifest(tmp_path: Path) -> None:
    run_benchmark(_fake_config(tmp_path))
    manifest_path = tmp_path / "run_manifest.json"
    original_manifest = manifest_path.read_text(encoding="utf-8")
    config = _fake_config(tmp_path, resume=True)
    config.timeout_sec = 61

    with pytest.raises(ValueError, match="resume manifest mismatch.*timeout_sec"):
        run_benchmark(config)

    assert manifest_path.read_text(encoding="utf-8") == original_manifest


def test_resume_rejects_missing_immutable_limit_before_rewriting_manifest(tmp_path: Path) -> None:
    run_benchmark(_fake_config(tmp_path))
    manifest_path = tmp_path / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("limit")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    original_manifest = manifest_path.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="resume manifest mismatch.*limit"):
        run_benchmark(_fake_config(tmp_path, resume=True))

    assert manifest_path.read_text(encoding="utf-8") == original_manifest


def test_checker_retry_forwards_remaining_solver_budget(monkeypatch) -> None:
    from nl2opt.checkers.base import CheckerReport

    observed_timeouts: list[float] = []

    def bounded_check(_spec: object, _result: object, *, timeout_sec: float) -> CheckerReport:
        observed_timeouts.append(timeout_sec)
        return CheckerReport(passed=True)

    monkeypatch.setattr(benchmark_module, "check_result_for_spec", bounded_check)
    attempt = BenchmarkAttempt(
        status="INFEASIBLE",
        checker_passed=False,
        spec=object(),
        solver_result=object(),
        details={"runtime_sec": 9.25},
    )
    config = BenchmarkRunConfig(checker_retry=True, timeout_sec=10)

    retried, checker_retried = benchmark_module._retry_checker(attempt, config)

    assert checker_retried is True
    assert retried.checker_passed is True
    assert observed_timeouts == [0.75]


@pytest.mark.parametrize("details", ({}, {"runtime_sec": 10}, {"runtime_sec": 12}))
def test_checker_retry_fails_closed_without_positive_remaining_budget(monkeypatch, details: dict[str, object]) -> None:
    from nl2opt.checkers.base import CheckerReport

    calls = 0

    def unbounded_check(*_args: object, **_kwargs: object) -> CheckerReport:
        nonlocal calls
        calls += 1
        return CheckerReport(passed=True)

    monkeypatch.setattr(benchmark_module, "check_result_for_spec", unbounded_check)
    attempt = BenchmarkAttempt(
        status="INFEASIBLE",
        checker_passed=False,
        spec=object(),
        solver_result=object(),
        details=details,
    )

    retried, checker_retried = benchmark_module._retry_checker(
        attempt,
        BenchmarkRunConfig(checker_retry=True, timeout_sec=10),
    )

    assert checker_retried is True
    assert retried.checker_passed is False
    assert "remaining" in (retried.error or "")
    assert calls == 0


def test_runner_rejects_incompatible_results_header_before_append(tmp_path: Path) -> None:
    config = _fake_config(tmp_path, resume=True)
    assert config.results_csv is not None
    config.results_csv.write_text("dataset,item_id\nnl4opt,item-0\n", encoding="utf-8")

    with pytest.raises(ValueError, match="results CSV header is incompatible with the current telemetry schema"):
        run_benchmark(config)


def test_pipeline_permission_error_is_classified_as_codegen_error(tmp_path: Path, monkeypatch) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())

    def successful_extraction(*_args: object, **_kwargs: object) -> ExtractorResult:
        return ExtractorResult(
            text="maximize x subject to x <= 1",
            problem_type="generic_lp_milp",
            success=True,
            spec=object(),
            spec_dict={},
            raw_response="{}",
            system_prompt="system",
            user_prompt="user",
            validation_errors=[],
            error=None,
            provider="fake-provider",
            model="fake-extractor",
            prompt_version="v4",
        )

    def denied_pipeline(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("cannot write solver output")

    monkeypatch.setattr(benchmark_module, "extract_problem_spec", successful_extraction)
    monkeypatch.setattr(benchmark_module, "run_problem_spec", denied_pipeline)

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            client=MockLLMClient({}),
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["status"] == "ERROR"
    assert row["failure_category"] == "CODEGEN_ERR"


def test_pipeline_error_preserves_response_backed_extractor_usage(tmp_path: Path, monkeypatch) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())
    usage = {"prompt_tokens": 19, "completion_tokens": 23, "total_tokens": 42}
    valid_spec = {
        "problem_id": "generic_schema",
        "problem_type": "generic_lp_milp",
        "variables": [{"name": "x", "lb": 0, "ub": 4, "is_integer": False}],
        "objective": {"sense": "maximize", "name": "value", "terms": [{"var": "x", "coef": 3}]},
        "constraints": [{"terms": [{"var": "x", "coef": 1}], "op": "<=", "rhs": 4}],
        "assumptions": [],
        "missing_fields": [],
    }

    def denied_pipeline(*_args: object, **_kwargs: object) -> object:
        raise PermissionError("cannot write solver output")

    monkeypatch.setattr(benchmark_module, "run_problem_spec", denied_pipeline)
    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            client=MockLLMClient(
                LLMResponse(
                    content=json.dumps(valid_spec),
                    provider="fake-provider",
                    model="fake-extractor",
                    usage=usage,
                )
            ),
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["status"] == "ERROR"
    assert json.loads(row["extractor_usage"]) == usage

    artifact = json.loads(Path(row["failure_artifact"]).read_text(encoding="utf-8"))
    assert artifact["extractor_usage"] == usage


def test_runner_saves_full_artifacts_only_for_failures(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows(2))

    def attempts(item, *_args):
        if item.item_id.endswith("0002"):
            return BenchmarkAttempt(status="ERROR", error="extraction failed")
        return _successful_attempt()

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            attempt_runner=attempts,
        )
    )

    artifact_paths = sorted((results.parent / "failures").glob("*.json"))
    assert len(artifact_paths) == 1
    assert "item-1" in artifact_paths[0].read_text(encoding="utf-8")


def test_runner_removes_successful_pipeline_work_artifacts(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())
    work_dir = tmp_path / "pipeline-work"
    work_dir.mkdir()
    (work_dir / "solution.json").write_text("full solver artifact", encoding="utf-8")

    def success_with_work(*_args):
        return BenchmarkAttempt(
            status="OPTIMAL",
            objective_value=1.0,
            checker_passed=True,
            details={"work_dir": str(work_dir)},
        )

    run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            attempt_runner=success_with_work,
        )
    )

    assert not work_dir.exists()


def test_translation_number_mismatch_blocks_extraction_and_records_failure(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=[{"id": "one", "en_question": "x <= 10", "en_answer": 10}])
    calls = 0

    class NumberChangingClient:
        def complete_json(self, *_args, **_kwargs):
            return LLMResponse(
                content=json.dumps({"translation": "x 小于等于 11"}, ensure_ascii=False),
                provider="fake",
                model="fake-translator",
                usage={"total_tokens": 3},
            )

    def should_not_run(*_args):
        nonlocal calls
        calls += 1
        return _successful_attempt()

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="zh",
            repetitions=1,
            client=NumberChangingClient(),
            attempt_runner=should_not_run,
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["status"] == "translation_number_mismatch"
    assert row["failure_category"] == "EXTRACT_ERR"
    assert row["translation_model"] == "fake-translator"
    assert row["extractor_usage"] == ""
    assert calls == 0
    assert len(list((results.parent / "failures").glob("*.json"))) == 1


def test_translation_audit_selection_is_deterministic_ten_percent(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows(10))

    class NumberPreservingClient:
        def complete_json(self, _system, prompt, **_kwargs):
            number = prompt.rsplit("<=", 1)[1].strip()
            return LLMResponse(
                content=json.dumps({"translation": f"x 小于等于 {number}"}, ensure_ascii=False),
                provider="fake",
                model="fake-translator",
            )

    first = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "first" / "results.csv",
            dataset="nl4opt",
            track="zh",
            repetitions=1,
            client=NumberPreservingClient(),
            attempt_runner=_successful_attempt,
        )
    )
    second = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "second" / "results.csv",
            dataset="nl4opt",
            track="zh",
            repetitions=1,
            client=NumberPreservingClient(),
            attempt_runner=_successful_attempt,
        )
    )

    def selected_items(path: Path) -> list[str]:
        return [row["item_id"] for row in csv.DictReader(path.open("r", newline="", encoding="utf-8"))]

    assert selected_items(first.parent / "translation_audit.csv") == selected_items(
        second.parent / "translation_audit.csv"
    )
    assert len(selected_items(first.parent / "translation_audit.csv")) == 1


def test_translation_audit_resume_does_not_append_duplicate_keys(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())

    class NumberPreservingClient:
        def complete_json(self, _system, prompt, **_kwargs):
            number = prompt.rsplit("<=", 1)[1].strip()
            return LLMResponse(
                content=json.dumps({"translation": f"x \u5c0f\u4e8e\u7b49\u4e8e {number}"}, ensure_ascii=False),
                provider="fake",
                model="fake-translator",
            )

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="zh",
            repetitions=1,
            client=NumberPreservingClient(),
            attempt_runner=_successful_attempt,
        )
    )
    results.write_text(
        ",".join(benchmark_module._RESULT_FIELDS) + "\n",
        encoding="utf-8",
    )

    run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=results,
            dataset="nl4opt",
            track="zh",
            repetitions=1,
            resume=True,
            client=NumberPreservingClient(),
            attempt_runner=_successful_attempt,
        )
    )

    audit_rows = list(csv.DictReader((results.parent / "translation_audit.csv").open("r", newline="", encoding="utf-8")))
    assert [(row["dataset"], row["item_id"], row["repetition"]) for row in audit_rows] == [
        ("nl4opt", "item-0", "1")
    ]


def test_runner_records_industryor_metadata_needed_for_reporting(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(
        datasets_dir,
        dataset="industryor",
        rows=[
            {
                "id": "industry-1",
                "en_question": "maximize x subject to x <= 1",
                "en_answer": 1,
                "difficulty": "Easy",
            }
        ],
    )

    class GenericSpec:
        problem_type = "generic_lp_milp"

    def successful_generic_attempt(*_args: object, **_kwargs: object) -> BenchmarkAttempt:
        return BenchmarkAttempt(
            status="OPTIMAL",
            objective_value=1.0,
            checker_passed=True,
            spec=GenericSpec(),
        )

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="industryor",
            track="en",
            repetitions=1,
            attempt_runner=successful_generic_attempt,
        )
    )

    row = next(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    assert row["difficulty"] == "Easy"
    assert row["problem_type"] == "generic_lp_milp"


def test_runner_manifest_records_limit_and_selected_item_scope(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows(2))

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            limit=1,
            attempt_runner=_successful_attempt,
        )
    )

    manifest = json.loads((results.parent / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["limit"] == 1
    assert manifest["selected_item_ids"] == {"nl4opt": ["item-0"]}


def test_runner_manifest_records_immutable_protocol_fields(tmp_path: Path) -> None:
    datasets_dir = tmp_path / "datasets"
    _write_dataset(datasets_dir, rows=_rows())

    results = run_benchmark(
        BenchmarkRunConfig(
            datasets_dir=datasets_dir,
            results_csv=tmp_path / "results.csv",
            dataset="nl4opt",
            track="en",
            repetitions=1,
            prompt_version="v4",
            temperature=0.0,
            requested_model="deepseek-unit-test",
            attempt_runner=_successful_attempt,
        )
    )

    manifest = json.loads((results.parent / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["prompt_version"] == "v4"
    assert manifest["temperature"] == 0.0
    assert manifest["requested_model"] == "deepseek-unit-test"


@pytest.mark.parametrize(
    ("field_name", "value"),
    (("prompt_version", "v5"), ("temperature", 0.1)),
)
def test_run_config_rejects_nonimmutable_prompt_protocol(field_name: str, value: object) -> None:
    with pytest.raises(ValueError, match=field_name):
        BenchmarkRunConfig(**{field_name: value})


def test_cli_exposes_the_benchmark_run_controls() -> None:
    args = build_parser().parse_args(
        [
            "--dataset",
            "industryor",
            "--track",
            "zh",
            "--repetitions",
            "2",
            "--checker-retry",
            "on",
            "--resume",
            "--limit",
            "5",
            "--timeout-sec",
            "30",
            "--run-id",
            "unit-test",
        ]
    )

    assert vars(args) == {
        "dataset": "industryor",
        "track": "zh",
        "repetitions": 2,
        "checker_retry": "on",
        "resume": True,
        "limit": 5,
        "timeout_sec": 30,
        "run_id": "unit-test",
    }
