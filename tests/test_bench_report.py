from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from nl2opt.eval.bench_report import build_parser as build_report_parser
from nl2opt.eval.bench_report import render_benchmark_report, wilson_interval


_RESULT_FIELDS = (
    "dataset",
    "item_id",
    "track",
    "repetition",
    "checker_retry",
    "status",
    "passed_1e_6",
    "passed_1e_4",
    "checker_retried",
    "failure_category",
    "router_problem_type",
    "extractor_provider",
    "extractor_model",
    "translation_usage",
    "extractor_usage",
    "judgment_reason",
    "difficulty",
    "problem_type",
)


def _write_inputs(
    tmp_path: Path,
    *,
    rows: list[dict[str, object]],
    audit_status: str,
    audit_items: list[tuple[str, str, int]] | None = None,
    checker_retry: str = "on",
    selected_item_ids: dict[str, list[str]] | None = None,
) -> tuple[Path, Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    selected_item_ids = selected_item_ids or {"nl4opt": ["n-1"], "industryor": ["i-1"]}
    results = tmp_path / "results.csv"
    with results.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "run_id": "unit-test",
                "dataset": "all",
                "track": "all",
                "repetitions": 3,
                "checker_retry": checker_retry,
                "limit": None,
                "timeout_sec": 60,
                "tolerance": 1e-6,
                "prompt_version": "v4",
                "temperature": 0.0,
                "requested_model": "deepseek-v4-flash",
                "started_at": "2026-07-10T00:00:00Z",
                "completed_at": "2026-07-10T00:10:00Z",
                "translation_audit_fraction": 0.10,
                "datasets": {
                    "nl4opt": {
                        "expected_nonblank_rows": 1,
                        "url": "https://example.test/nl4opt",
                        "revision": "pinned-nl4opt",
                        "sha256": "0" * 64,
                        "license": "Apache-2.0",
                    },
                    "industryor": {
                        "expected_nonblank_rows": 1,
                        "url": "https://example.test/industryor",
                        "revision": "pinned-industryor",
                        "sha256": "1" * 64,
                        "license": "Apache-2.0",
                    },
                },
                "selected_item_ids": selected_item_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    audit = tmp_path / "translation_audit.csv"
    audit_items = audit_items or [
        (dataset, item_id, repetition)
        for dataset, item_ids in selected_item_ids.items()
        for item_id in item_ids
        for repetition in range(1, 4)
    ]
    with audit.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "dataset",
                "item_id",
                "repetition",
                "numbers_match",
                "human_audit_status",
                "human_audit_notes",
            ),
        )
        writer.writeheader()
        for dataset, item_id, repetition in audit_items:
            writer.writerow(
                {
                    "dataset": dataset,
                    "item_id": item_id,
                    "repetition": repetition,
                    "numbers_match": "True",
                    "human_audit_status": audit_status,
                    "human_audit_notes": "reviewed by a human",
                }
            )
    return results, manifest, audit


def _result_rows(
    *,
    checker_retry: str = "on",
    nl4opt_item_id: str = "n-1",
    industryor_item_id: str = "i-1",
) -> list[dict[str, object]]:
    rows = []
    for repetition in range(1, 4):
        for dataset, item_id in (("nl4opt", nl4opt_item_id), ("industryor", industryor_item_id)):
            for track in ("en", "zh"):
                strict_passed = True
                loose_passed = True
                status = "OPTIMAL"
                reason = "objective_match"
                checker_retried = False
                failure_category = ""
                if (dataset, track, repetition) == ("industryor", "zh", 1):
                    strict_passed = False
                    loose_passed = False
                    status = "EXTRACTION_ERROR"
                    reason = "checker_failed"
                    checker_retried = checker_retry == "on"
                    failure_category = "EXTRACT_ERR"
                elif (dataset, track, repetition) == ("industryor", "en", 2):
                    strict_passed = False
                    reason = "objective_mismatch"
                    failure_category = "WRONG_OPT"
                row: dict[str, object] = {
                    "dataset": dataset,
                    "item_id": item_id,
                    "track": track,
                    "repetition": repetition,
                    "checker_retry": checker_retry,
                    "status": status,
                    "passed_1e_6": strict_passed,
                    "passed_1e_4": loose_passed,
                    "checker_retried": checker_retried,
                    "failure_category": failure_category,
                    "router_problem_type": "generic_lp_milp",
                    "extractor_provider": "deepseek",
                    "extractor_model": "deepseek-v4-flash",
                    "translation_usage": json.dumps(
                        {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}
                    ),
                    "extractor_usage": json.dumps(
                        {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 18}
                    ),
                    "judgment_reason": reason,
                }
                if dataset == "industryor":
                    row.update({"difficulty": "Easy", "problem_type": "linear_programming"})
                rows.append(row)
    return rows


def _rewrite_result_rows(
    path: Path, rows: list[dict[str, str]], fieldnames: tuple[str, ...] = _RESULT_FIELDS
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def test_wilson_interval_for_all_successes_is_bounded() -> None:
    low, high = wilson_interval(10, 10)

    assert 0 < low < 1
    assert high == 1


def test_wilson_interval_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError, match="successes"):
        wilson_interval(3, 2)

    with pytest.raises(ValueError, match="total"):
        wilson_interval(0, 0)


def test_report_refuses_incomplete_translation_audit(tmp_path: Path) -> None:
    results, manifest, incomplete_audit = _write_inputs(
        tmp_path,
        rows=_result_rows(),
        audit_status="pending",
    )
    output = tmp_path / "report.md"

    with pytest.raises(ValueError, match="audit"):
        render_benchmark_report(results, manifest, incomplete_audit, output)

    assert not output.exists()


def test_report_refuses_missing_deterministic_audit_row(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(
        tmp_path,
        rows=_result_rows(),
        audit_status="approved",
        audit_items=[("industryor", "i-1", 1)],
    )

    with pytest.raises(ValueError, match="audit"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_requires_exactly_ten_percent_audit_fraction(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["translation_audit_fraction"] = 0.01
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="0.10"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_refuses_limited_run(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["limit"] = 1
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="limit"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_requires_both_tracks(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["track"] = "en"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="both en and zh"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_requires_exactly_three_repetitions(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["repetitions"] = 2
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly 3"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


@pytest.mark.parametrize(
    ("field_name", "value"),
    (
        ("timeout_sec", 59),
        ("timeout_sec", "60"),
        ("timeout_sec", float("nan")),
        ("tolerance", 1e-4),
        ("tolerance", "1e-6"),
        ("tolerance", float("inf")),
        ("prompt_version", "v3"),
        ("prompt_version", None),
        ("temperature", 0.1),
        ("temperature", "0.0"),
        ("temperature", float("nan")),
        ("requested_model", ""),
        ("requested_model", None),
    ),
)
def test_report_rejects_nonstandard_or_missing_public_protocol(
    tmp_path: Path, field_name: str, value: object
) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload[field_name] = value
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=field_name):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


@pytest.mark.parametrize("field_name", ("timeout_sec", "tolerance", "prompt_version", "temperature", "requested_model"))
def test_report_rejects_missing_public_protocol_field(tmp_path: Path, field_name: str) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.pop(field_name)
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=field_name):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_refuses_incomplete_public_matrix(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows()[:-1], audit_status="approved")

    with pytest.raises(ValueError, match="matrix"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_refuses_duplicate_public_matrix_key(tmp_path: Path) -> None:
    rows = _result_rows()
    results, manifest, audit = _write_inputs(tmp_path, rows=rows + [rows[0]], audit_status="approved")

    with pytest.raises(ValueError, match="duplicate"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_refuses_duplicate_translation_audit_key(tmp_path: Path) -> None:
    audit_items = [
        (dataset, item_id, repetition)
        for dataset, item_id in (("nl4opt", "n-1"), ("industryor", "i-1"))
        for repetition in range(1, 4)
    ]
    results, manifest, audit = _write_inputs(
        tmp_path,
        rows=_result_rows(),
        audit_status="approved",
        audit_items=[*audit_items, ("nl4opt", "n-1", 1)],
    )

    with pytest.raises(ValueError, match="duplicate translation audit key"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_uses_chinese_primary_body(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    output = tmp_path / "report.md"

    render_benchmark_report(results, manifest, audit, output)

    report = output.read_text(encoding="utf-8")
    assert "## English executive summary" in report
    assert "## 双轨结果" in report
    assert "| 数据集 | 语言轨道 | 尝试次数 | 严格通过 | 通过率 |" in report
    assert "## 按重复次数的 Wilson 置信区间" in report
    assert "## 局限性" in report
    assert "## 文献与数据集来源" in report
    assert "## Dual-track results" not in report


def test_report_renders_audited_dual_track_snapshot(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    output = tmp_path / "report.md"

    rendered = render_benchmark_report(results, manifest, audit, output)

    assert rendered == output
    report = output.read_text(encoding="utf-8")
    assert "# 公共基准测试报告" in report
    assert "## English executive summary" in report
    assert "## 双轨结果" in report
    assert "| industryor | zh | 3 | 2 | 66.7% |" in report
    assert "## 按重复次数的 Wilson 置信区间" in report
    assert "| 1 | 4 | 3 | 75.0% |" in report
    assert "## IndustryOR 类型/难度分解" in report
    assert "| Easy | linear_programming | 6 | 4 | 66.7% |" in report
    assert "## 失败分布" in report
    assert "| 失败类型 | 数量 |" in report
    assert "| EXTRACT_ERR | 1 |" in report
    assert "2026-07-10T00:00:00Z" in report
    assert "2026-07-10T00:10:00Z" in report
    assert "deepseek-v4-flash" in report
    assert "translation total=60" in report
    assert "extractor total=216" in report
    assert "## 1e-4 敏感性" in report
    assert "| 严格 1e-6 | 10 | 12 | 83.3% |" in report
    assert "| 宽松 1e-4 | 11 | 12 | 91.7% |" in report
    assert "## Checker 重试消融" in report
    assert "| 开启 | 10 | 12 | 83.3% |" in report
    assert "## 局限性" in report
    assert "## 文献与数据集来源" in report
    assert "本报告未使用外部基准性能数值" in report
    assert "https://example.test/nl4opt" in report


def test_report_renders_two_complete_checker_retry_runs_as_an_ablation(tmp_path: Path) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off",
        rows=_result_rows(checker_retry="off"),
        audit_status="approved",
        checker_retry="off",
    )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on",
        rows=_result_rows(checker_retry="on"),
        audit_status="approved",
        checker_retry="on",
    )
    output = tmp_path / "report.md"

    render_benchmark_report(
        primary_results,
        primary_manifest,
        primary_audit,
        output,
        comparison_results_csv=comparison_results,
        comparison_run_manifest=comparison_manifest,
        comparison_audit_csv=comparison_audit,
    )

    report = output.read_text(encoding="utf-8")
    assert "Checker 重试消融尚待完成" not in report
    assert "| 关闭 | 10 | 12 | 83.3% | 0 |" in report
    assert "| 开启 | 10 | 12 | 83.3% | 1 |" in report


def test_report_rejects_retry_comparison_with_incompatible_dataset_revision(tmp_path: Path) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off",
        rows=_result_rows(checker_retry="off"),
        audit_status="approved",
        checker_retry="off",
    )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on",
        rows=_result_rows(checker_retry="on"),
        audit_status="approved",
        checker_retry="on",
    )
    comparison_payload = json.loads(comparison_manifest.read_text(encoding="utf-8"))
    comparison_payload["datasets"]["nl4opt"]["revision"] = "different-revision"
    comparison_manifest.write_text(json.dumps(comparison_payload), encoding="utf-8")

    with pytest.raises(ValueError, match="dataset revisions"):
        render_benchmark_report(
            primary_results,
            primary_manifest,
            primary_audit,
            tmp_path / "report.md",
            comparison_results_csv=comparison_results,
            comparison_run_manifest=comparison_manifest,
            comparison_audit_csv=comparison_audit,
        )


def test_report_rejects_retry_comparison_with_incompatible_selected_item_scope(tmp_path: Path) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off",
        rows=_result_rows(checker_retry="off"),
        audit_status="approved",
        checker_retry="off",
    )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on",
        rows=_result_rows(checker_retry="on", nl4opt_item_id="n-2"),
        audit_status="approved",
        checker_retry="on",
        selected_item_ids={"nl4opt": ["n-2"], "industryor": ["i-1"]},
    )

    with pytest.raises(ValueError, match="selected item IDs"):
        render_benchmark_report(
            primary_results,
            primary_manifest,
            primary_audit,
            tmp_path / "report.md",
            comparison_results_csv=comparison_results,
            comparison_run_manifest=comparison_manifest,
            comparison_audit_csv=comparison_audit,
        )


@pytest.mark.parametrize(
    ("path", "replacement"),
    (
        (("dataset",), "nl4opt"),
        (("timeout_sec",), 61),
        (("tolerance",), 1e-4),
        (("prompt_version",), "v3"),
        (("temperature",), 0.1),
        (("requested_model",), "another-model"),
        (("datasets", "nl4opt", "sha256"), "2" * 64),
        (("datasets", "nl4opt", "revision"), "other-revision"),
        (("datasets", "nl4opt", "url"), "https://example.test/other"),
        (("datasets", "nl4opt", "license"), "MIT"),
        (("datasets", "nl4opt", "expected_nonblank_rows"), 1.0),
    ),
)
def test_report_rejects_every_retry_comparison_protocol_or_dataset_mismatch(
    tmp_path: Path, path: tuple[str, ...], replacement: object
) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off", rows=_result_rows(checker_retry="off"), audit_status="approved", checker_retry="off"
    )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on", rows=_result_rows(checker_retry="on"), audit_status="approved", checker_retry="on"
    )
    payload = json.loads(comparison_manifest.read_text(encoding="utf-8"))
    destination = payload
    for component in path[:-1]:
        destination = destination[component]
    destination[path[-1]] = replacement
    comparison_manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        render_benchmark_report(
            primary_results,
            primary_manifest,
            primary_audit,
            tmp_path / "report.md",
            comparison_results_csv=comparison_results,
            comparison_run_manifest=comparison_manifest,
            comparison_audit_csv=comparison_audit,
        )


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    (("extractor_provider", "different-provider"), ("extractor_model", "another-model")),
)
def test_report_rejects_retry_comparison_with_mismatched_actual_extractor_set(
    tmp_path: Path, field_name: str, replacement: str
) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off", rows=_result_rows(checker_retry="off"), audit_status="approved", checker_retry="off"
    )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on", rows=_result_rows(checker_retry="on"), audit_status="approved", checker_retry="on"
    )
    rows = list(csv.DictReader(comparison_results.open("r", newline="", encoding="utf-8")))
    for row in rows:
        row[field_name] = replacement
    _rewrite_result_rows(comparison_results, rows)

    with pytest.raises(ValueError, match="actual extractor"):
        render_benchmark_report(
            primary_results,
            primary_manifest,
            primary_audit,
            tmp_path / "report.md",
            comparison_results_csv=comparison_results,
            comparison_run_manifest=comparison_manifest,
            comparison_audit_csv=comparison_audit,
        )


def test_report_rejects_empty_actual_extractor_metadata(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    rows = list(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    for row in rows:
        row["extractor_provider"] = ""
        row["extractor_model"] = ""
    _rewrite_result_rows(results, rows)

    with pytest.raises(ValueError, match="actual extractor"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_requires_failure_category_column(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    rows = list(csv.DictReader(results.open("r", newline="", encoding="utf-8")))
    fields = tuple(field for field in _RESULT_FIELDS if field != "failure_category")
    _rewrite_result_rows(results, rows, fields)

    with pytest.raises(ValueError, match="failure_category"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_requires_failure_category_for_each_strict_failure(tmp_path: Path) -> None:
    rows = _result_rows()
    failed_row = next(row for row in rows if not row["passed_1e_6"])
    failed_row["failure_category"] = ""
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")

    with pytest.raises(ValueError, match="failure_category"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


@pytest.mark.parametrize(
    ("provider", "model"),
    (("", ""), ("", "deepseek-v4-flash"), ("deepseek", "")),
)
def test_report_rejects_blank_or_partial_actual_metadata_after_extraction(
    tmp_path: Path, provider: str, model: str
) -> None:
    rows = _result_rows()
    rows[0]["extractor_provider"] = provider
    rows[0]["extractor_model"] = model
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")

    with pytest.raises(ValueError, match="actual extractor"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_allows_explicit_router_unsupported_without_extractor_metadata(tmp_path: Path) -> None:
    rows = _result_rows()
    unsupported_row = rows[0]
    unsupported_row.update(
        {
            "status": "UNSUPPORTED",
            "passed_1e_6": False,
            "passed_1e_4": False,
            "failure_category": "UNSUPPORTED",
            "router_problem_type": "unsupported",
            "extractor_provider": "",
            "extractor_model": "",
            "extractor_usage": "",
        }
    )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")

    render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_keeps_exhausted_extractor_api_failure_without_actual_identity_in_denominator(
    tmp_path: Path,
) -> None:
    rows = _result_rows()
    rows[0].update(
        {
            "status": "API_ERROR",
            "passed_1e_6": False,
            "passed_1e_4": False,
            "failure_category": "API_ERR",
            "extractor_provider": "",
            "extractor_model": "",
            "extractor_usage": "",
        }
    )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")
    output = tmp_path / "report.md"

    render_benchmark_report(results, manifest, audit, output)

    report = output.read_text(encoding="utf-8")
    assert "contains 12 attempts" in report
    assert "| API_ERR | 1 |" in report


@pytest.mark.parametrize("status", ("translation_error", "translation_number_mismatch"))
def test_report_keeps_pre_extraction_translation_failure_without_actual_identity_in_denominator(
    tmp_path: Path, status: str
) -> None:
    rows = _result_rows()
    rows[0].update(
        {
            "status": status,
            "passed_1e_6": False,
            "passed_1e_4": False,
            "failure_category": "EXTRACT_ERR",
            "extractor_provider": "",
            "extractor_model": "",
            "extractor_usage": "",
        }
    )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")
    output = tmp_path / "report.md"

    render_benchmark_report(results, manifest, audit, output)

    report = output.read_text(encoding="utf-8")
    assert "contains 12 attempts" in report
    assert "| EXTRACT_ERR | 2 |" in report


@pytest.mark.parametrize(
    ("status", "failure_category", "router_problem_type"),
    (
        ("UNSUPPORTED", "UNSUPPORTED", "unsupported"),
        ("API_ERROR", "API_ERR", "generic_lp_milp"),
        ("translation_error", "EXTRACT_ERR", "generic_lp_milp"),
        ("translation_number_mismatch", "EXTRACT_ERR", "generic_lp_milp"),
    ),
)
@pytest.mark.parametrize(
    ("provider", "model"),
    (("deepseek", ""), ("", "deepseek-v4-flash")),
)
def test_report_rejects_partial_actual_identity_on_every_unavailable_identity_path(
    tmp_path: Path,
    status: str,
    failure_category: str,
    router_problem_type: str,
    provider: str,
    model: str,
) -> None:
    rows = _result_rows()
    rows[0].update(
        {
            "status": status,
            "passed_1e_6": False,
            "passed_1e_4": False,
            "failure_category": failure_category,
            "router_problem_type": router_problem_type,
            "extractor_provider": provider,
            "extractor_model": model,
        }
    )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")

    with pytest.raises(ValueError, match="provider/model pairs"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


@pytest.mark.parametrize(
    ("status", "failure_category"),
    (("OPTIMAL", ""), ("EXTRACTION_ERROR", "EXTRACT_ERR"), ("SOLVE_TIMEOUT", "SOLVE_TIMEOUT")),
)
def test_report_rejects_blank_actual_identity_after_extraction_or_downstream_processing(
    tmp_path: Path, status: str, failure_category: str
) -> None:
    rows = _result_rows()
    rows[0].update(
        {
            "status": status,
            "passed_1e_6": status == "OPTIMAL",
            "passed_1e_4": status == "OPTIMAL",
            "failure_category": failure_category,
            "extractor_provider": "",
            "extractor_model": "",
        }
    )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")

    with pytest.raises(ValueError, match="actual extractor"):
        render_benchmark_report(results, manifest, audit, tmp_path / "report.md")


def test_report_provenance_discloses_exact_unavailable_actual_identity_count(tmp_path: Path) -> None:
    rows = _result_rows()
    for row, status, failure_category in (
        (rows[0], "API_ERROR", "API_ERR"),
        (rows[1], "translation_error", "EXTRACT_ERR"),
        (rows[2], "translation_number_mismatch", "EXTRACT_ERR"),
    ):
        row.update(
            {
                "status": status,
                "passed_1e_6": False,
                "passed_1e_4": False,
                "failure_category": failure_category,
                "extractor_provider": "",
                "extractor_model": "",
                "extractor_usage": "",
            }
        )
    results, manifest, audit = _write_inputs(tmp_path, rows=rows, audit_status="approved")
    output = tmp_path / "report.md"

    render_benchmark_report(results, manifest, audit, output)

    report = output.read_text(encoding="utf-8")
    assert "- Actual extractor identity unavailable (no usable extractor response): `3` rows" in report
    assert "- Actual extractor provider/model set: `deepseek/deepseek-v4-flash`" in report
    assert "- Requested model: `deepseek-v4-flash`" in report


def test_report_retry_comparison_accepts_different_legitimate_unavailable_identity_counts(
    tmp_path: Path,
) -> None:
    primary_rows = _result_rows(checker_retry="off")
    primary_rows[0].update(
        {
            "status": "API_ERROR",
            "passed_1e_6": False,
            "passed_1e_4": False,
            "failure_category": "API_ERR",
            "extractor_provider": "",
            "extractor_model": "",
        }
    )
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off", rows=primary_rows, audit_status="approved", checker_retry="off"
    )
    comparison_rows = _result_rows(checker_retry="on")
    for row in comparison_rows[:2]:
        row.update(
            {
                "status": "translation_error",
                "passed_1e_6": False,
                "passed_1e_4": False,
                "failure_category": "EXTRACT_ERR",
                "extractor_provider": "",
                "extractor_model": "",
            }
        )
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on", rows=comparison_rows, audit_status="approved", checker_retry="on"
    )
    output = tmp_path / "report.md"

    render_benchmark_report(
        primary_results,
        primary_manifest,
        primary_audit,
        output,
        comparison_results_csv=comparison_results,
        comparison_run_manifest=comparison_manifest,
        comparison_audit_csv=comparison_audit,
    )

    report = output.read_text(encoding="utf-8")
    assert "- Actual extractor identity unavailable (no usable extractor response): `1` rows" in report


def test_report_rejects_comparison_blank_actual_metadata_after_extraction(tmp_path: Path) -> None:
    primary_results, primary_manifest, primary_audit = _write_inputs(
        tmp_path / "off", rows=_result_rows(checker_retry="off"), audit_status="approved", checker_retry="off"
    )
    comparison_rows = _result_rows(checker_retry="on")
    comparison_rows[0]["extractor_provider"] = ""
    comparison_rows[0]["extractor_model"] = ""
    comparison_results, comparison_manifest, comparison_audit = _write_inputs(
        tmp_path / "on", rows=comparison_rows, audit_status="approved", checker_retry="on"
    )

    with pytest.raises(ValueError, match="actual extractor"):
        render_benchmark_report(
            primary_results,
            primary_manifest,
            primary_audit,
            tmp_path / "report.md",
            comparison_results_csv=comparison_results,
            comparison_run_manifest=comparison_manifest,
            comparison_audit_csv=comparison_audit,
        )


def test_report_marks_checker_retry_ablation_pending_without_comparison_artifacts(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    output = tmp_path / "report.md"

    render_benchmark_report(results, manifest, audit, output)

    report = output.read_text(encoding="utf-8")
    assert "Checker 重试消融尚待完成" in report
    assert "不声明该消融已运行" in report


def test_report_cli_accepts_primary_and_optional_comparison_artifacts() -> None:
    args = build_report_parser().parse_args(
        [
            "--results-csv",
            "off/results.csv",
            "--run-manifest",
            "off/run_manifest.json",
            "--audit-csv",
            "off/translation_audit.csv",
            "--output",
            "report.md",
            "--comparison-results-csv",
            "on/results.csv",
            "--comparison-run-manifest",
            "on/run_manifest.json",
            "--comparison-audit-csv",
            "on/translation_audit.csv",
        ]
    )

    assert vars(args) == {
        "results_csv": Path("off/results.csv"),
        "run_manifest": Path("off/run_manifest.json"),
        "audit_csv": Path("off/translation_audit.csv"),
        "output": Path("report.md"),
        "comparison_results_csv": Path("on/results.csv"),
        "comparison_run_manifest": Path("on/run_manifest.json"),
        "comparison_audit_csv": Path("on/translation_audit.csv"),
    }


def test_readme_declares_strict_generic_lp_milp_support_and_refusal_boundary() -> None:
    content = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert "`generic_lp_milp`" in content
    assert "strictly linear LP/IP/MIP" in content
    assert "GLOP" in content
    assert "SCIP" in content
    assert "nonlinear, stochastic, dynamic" in content
    assert "refused rather than silently modeled" in content
    assert "20/20" in content
    assert "not a public-benchmark result" in content


def test_claim_registry_leaves_public_metrics_as_a_template() -> None:
    registry = Path(__file__).parents[1] / "docs" / "claim_registry.md"
    content = registry.read_text(encoding="utf-8")

    assert "Public benchmark result (pending audited run)" in content
    assert "NL4Opt/IndustryOR" in content
    assert "Do not replace this template" in content
