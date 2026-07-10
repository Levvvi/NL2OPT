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
                "translation_audit_fraction": 0.10,
                "datasets": {
                    "nl4opt": {
                        "expected_nonblank_rows": 1,
                        "url": "https://example.test/nl4opt",
                        "revision": "pinned-nl4opt",
                        "license": "Apache-2.0",
                    },
                    "industryor": {
                        "expected_nonblank_rows": 1,
                        "url": "https://example.test/industryor",
                        "revision": "pinned-industryor",
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
                if (dataset, track, repetition) == ("industryor", "zh", 1):
                    strict_passed = False
                    loose_passed = False
                    status = "EXTRACTION_ERROR"
                    reason = "checker_failed"
                    checker_retried = checker_retry == "on"
                elif (dataset, track, repetition) == ("industryor", "en", 2):
                    strict_passed = False
                    reason = "objective_mismatch"
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
                    "judgment_reason": reason,
                }
                if dataset == "industryor":
                    row.update({"difficulty": "Easy", "problem_type": "linear_programming"})
                rows.append(row)
    return rows


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
    assert "| EXTRACTION_ERROR | 1 |" in report
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


def test_claim_registry_leaves_public_metrics_as_a_template() -> None:
    registry = Path(__file__).parents[1] / "docs" / "claim_registry.md"
    content = registry.read_text(encoding="utf-8")

    assert "Public benchmark result (pending audited run)" in content
    assert "NL4Opt/IndustryOR" in content
    assert "Do not replace this template" in content
