from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

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
) -> tuple[Path, Path, Path]:
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
                "repetitions": 2,
                "checker_retry": "on",
                "timeout_sec": 60,
                "tolerance": 1e-6,
                "translation_audit_fraction": 0.10,
                "datasets": {
                    "nl4opt": {
                        "url": "https://example.test/nl4opt",
                        "revision": "pinned-nl4opt",
                        "license": "Apache-2.0",
                    },
                    "industryor": {
                        "url": "https://example.test/industryor",
                        "revision": "pinned-industryor",
                        "license": "Apache-2.0",
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    audit = tmp_path / "translation_audit.csv"
    audit_items = audit_items or [("nl4opt", "n-1", 1), ("industryor", "i-1", 1), ("industryor", "i-2", 2)]
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


def _result_rows() -> list[dict[str, object]]:
    return [
        {
            "dataset": "nl4opt",
            "item_id": "n-1",
            "track": "en",
            "repetition": 1,
            "checker_retry": "on",
            "status": "OPTIMAL",
            "passed_1e_6": True,
            "passed_1e_4": True,
            "checker_retried": False,
            "judgment_reason": "objective_match",
        },
        {
            "dataset": "nl4opt",
            "item_id": "n-1",
            "track": "zh",
            "repetition": 1,
            "checker_retry": "on",
            "status": "OPTIMAL",
            "passed_1e_6": True,
            "passed_1e_4": True,
            "checker_retried": False,
            "judgment_reason": "objective_match",
        },
        {
            "dataset": "industryor",
            "item_id": "i-1",
            "track": "en",
            "repetition": 1,
            "checker_retry": "on",
            "status": "OPTIMAL",
            "passed_1e_6": True,
            "passed_1e_4": True,
            "checker_retried": False,
            "judgment_reason": "objective_match",
            "difficulty": "Easy",
            "problem_type": "linear_programming",
        },
        {
            "dataset": "industryor",
            "item_id": "i-1",
            "track": "zh",
            "repetition": 1,
            "checker_retry": "on",
            "status": "EXTRACTION_ERROR",
            "passed_1e_6": False,
            "passed_1e_4": False,
            "checker_retried": True,
            "judgment_reason": "checker_failed",
            "difficulty": "Easy",
            "problem_type": "linear_programming",
        },
        {
            "dataset": "industryor",
            "item_id": "i-2",
            "track": "en",
            "repetition": 2,
            "checker_retry": "off",
            "status": "OPTIMAL",
            "passed_1e_6": False,
            "passed_1e_4": True,
            "checker_retried": False,
            "judgment_reason": "objective_mismatch",
            "difficulty": "Hard",
            "problem_type": "integer_programming",
        },
        {
            "dataset": "industryor",
            "item_id": "i-2",
            "track": "zh",
            "repetition": 2,
            "checker_retry": "off",
            "status": "OPTIMAL",
            "passed_1e_6": True,
            "passed_1e_4": True,
            "checker_retried": True,
            "judgment_reason": "objective_match",
            "difficulty": "Hard",
            "problem_type": "integer_programming",
        },
    ]


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


def test_report_renders_audited_dual_track_snapshot(tmp_path: Path) -> None:
    results, manifest, audit = _write_inputs(tmp_path, rows=_result_rows(), audit_status="approved")
    output = tmp_path / "report.md"

    rendered = render_benchmark_report(results, manifest, audit, output)

    assert rendered == output
    report = output.read_text(encoding="utf-8")
    assert "# Public Benchmark Report" in report
    assert "## Executive summary" in report
    assert "## 中文结果摘要" in report
    assert "## Dual-track results" in report
    assert "| industryor | zh | 2 | 1 | 50.0% |" in report
    assert "## Per-repetition Wilson intervals" in report
    assert "| 1 | 4 | 3 | 75.0% |" in report
    assert "## IndustryOR type/difficulty decomposition" in report
    assert "| Easy | linear_programming | 2 | 1 | 50.0% |" in report
    assert "| Hard | integer_programming | 2 | 1 | 50.0% |" in report
    assert "## Failure distribution" in report
    assert "| EXTRACTION_ERROR | 1 |" in report
    assert "## 1e-4 sensitivity" in report
    assert "| strict 1e-6 | 4 | 6 | 66.7% |" in report
    assert "| loose 1e-4 | 5 | 6 | 83.3% |" in report
    assert "## Checker-retry ablation" in report
    assert "| on | 3 | 4 | 75.0% |" in report
    assert "| off | 1 | 2 | 50.0% |" in report
    assert "## Limitations" in report
    assert "## Literature and dataset references" in report
    assert "No external benchmark performance value is used" in report
    assert "https://example.test/nl4opt" in report


def test_claim_registry_leaves_public_metrics_as_a_template() -> None:
    registry = Path(__file__).parents[1] / "docs" / "claim_registry.md"
    content = registry.read_text(encoding="utf-8")

    assert "Public benchmark result (pending audited run)" in content
    assert "NL4Opt/IndustryOR" in content
    assert "Do not replace this template" in content
