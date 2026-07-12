from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from nl2opt.eval.publication_export import RunExpectation, build_parser, export_publication_package


RESULT_FIELDS = (
    "dataset",
    "item_id",
    "track",
    "repetition",
    "checker_retry",
    "passed_1e_6",
    "passed_1e_4",
    "checker_retried",
    "failure_category",
    "failure_artifact",
    "error",
)
AUDIT_FIELDS = (
    "dataset",
    "item_id",
    "repetition",
    "numbers_match",
    "human_audit_status",
    "human_audit_notes",
)


def _write_run(
    root: Path,
    run_id: str,
    mode: str,
    *,
    secret: str = "",
) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    rows = [
        {
            "dataset": "nl4opt",
            "item_id": "n-1",
            "track": "en",
            "repetition": "1",
            "checker_retry": mode,
            "passed_1e_6": "True",
            "passed_1e_4": "True",
            "checker_retried": "False",
            "failure_category": "",
            "failure_artifact": "",
            "error": secret,
        },
        {
            "dataset": "nl4opt",
            "item_id": "n-1",
            "track": "zh",
            "repetition": "1",
            "checker_retry": mode,
            "passed_1e_6": "False",
            "passed_1e_4": "False",
            "checker_retried": str(mode == "on"),
            "failure_category": "EXTRACT_ERR",
            "failure_artifact": rf"C:\Users\private-user\repo\eval\results\{run_id}\failures\n-1-zh.json",
            "error": "schema validation failed",
        },
    ]
    with (run / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (run / "translation_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerow(
            {
                "dataset": "nl4opt",
                "item_id": "n-1",
                "repetition": "1",
                "numbers_match": "False",
                "human_audit_status": "rejected",
                "human_audit_notes": "reviewed",
            }
        )
    (run / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "checker_retry": mode,
                "completed_at": "2026-07-12T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    return run


def _expectation(mode: str) -> RunExpectation:
    return RunExpectation(
        checker_retry=mode,
        result_rows=2,
        audit_rows=1,
        strict_passes=1,
        loose_passes=1,
        audit_status_counts={"approved": 0, "rejected": 1, "waived": 0},
        checker_retries=1 if mode == "on" else 0,
    )


def test_export_publication_package_sanitizes_paths_and_records_hashes(tmp_path: Path) -> None:
    off = _write_run(tmp_path / "inputs", "retry-off", "off")
    on = _write_run(tmp_path / "inputs", "retry-on", "on")
    output = tmp_path / "publication"

    manifest_path = export_publication_package(
        [off, on],
        output,
        expectations={"retry-off": _expectation("off"), "retry-on": _expectation("on")},
    )

    package = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert [run["run_id"] for run in package["runs"]] == ["retry-off", "retry-on"]
    assert package["runs"][0]["strict_passes"] == 1
    assert package["runs"][0]["strict_rate"] == 0.5
    assert package["runs"][1]["checker_retry_count"] == 1
    assert package["runs"][0]["audit_status_counts"] == {"approved": 0, "rejected": 1, "waived": 0}
    for run in package["runs"]:
        run_dir = output / run["run_id"]
        assert set(path.name for path in run_dir.iterdir()) == {
            "results.csv",
            "run_manifest.json",
            "translation_audit.csv",
        }
        for filename, metadata in run["files"].items():
            path = run_dir / filename
            assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        rows = list(csv.DictReader((run_dir / "results.csv").open("r", newline="", encoding="utf-8")))
        assert rows[1]["failure_artifact"] == "failures/n-1-zh.json"
    published = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*.*"))
    assert "C:\\Users\\" not in published
    assert "private-user" not in published
    assert "complete failure JSON archives remain local" in (output / "README.md").read_text(encoding="utf-8")


def test_export_replaces_stale_output_with_exact_closed_file_set(tmp_path: Path) -> None:
    off = _write_run(tmp_path / "inputs", "retry-off", "off")
    on = _write_run(tmp_path / "inputs", "retry-on", "on")
    output = tmp_path / "publication"
    (output / "obsolete-run").mkdir(parents=True)
    (output / "obsolete-run" / "results.csv").write_text(
        r"C:\Users\private-user\obsolete", encoding="utf-8"
    )
    (output / "retry-off").mkdir()
    (output / "retry-off" / "stale-private.json").write_text(
        "api_key=sk-1234567890abcdef", encoding="utf-8"
    )

    export_publication_package(
        [off, on],
        output,
        expectations={"retry-off": _expectation("off"), "retry-on": _expectation("on")},
    )

    relative_files = {
        path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()
    }
    assert relative_files == {
        "README.md",
        "manifest.json",
        "retry-off/results.csv",
        "retry-off/run_manifest.json",
        "retry-off/translation_audit.csv",
        "retry-on/results.csv",
        "retry-on/run_manifest.json",
        "retry-on/translation_audit.csv",
    }
    published = "\n".join(path.read_text(encoding="utf-8") for path in output.rglob("*") if path.is_file())
    assert "private-user" not in published
    assert "sk-1234567890abcdef" not in published


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("duplicate_result", "duplicate result key"),
        ("incomplete_manifest", "completed manifest"),
        ("wrong_mode", "checker-retry mode"),
        ("pending_audit", "terminal"),
        ("duplicate_audit", "duplicate audit key"),
        ("wrong_count", "result row count"),
        ("secret", "credential-like"),
    ],
)
def test_export_validation_and_privacy_fail_before_writing(
    tmp_path: Path, mutation: str, message: str
) -> None:
    secret = "api_key=sk-1234567890abcdef" if mutation == "secret" else ""
    run = _write_run(tmp_path / "inputs", "retry-off", "off", secret=secret)
    expectation = _expectation("off")
    if mutation == "duplicate_result":
        rows = list(csv.DictReader((run / "results.csv").open("r", newline="", encoding="utf-8")))
        with (run / "results.csv").open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=RESULT_FIELDS).writerow(rows[0])
        expectation = RunExpectation(**{**expectation.__dict__, "result_rows": 3})
    elif mutation == "incomplete_manifest":
        payload = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        payload["completed_at"] = None
        (run / "run_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "wrong_mode":
        payload = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
        payload["checker_retry"] = "on"
        (run / "run_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "pending_audit":
        rows = list(csv.DictReader((run / "translation_audit.csv").open("r", newline="", encoding="utf-8")))
        rows[0]["human_audit_status"] = "pending"
        with (run / "translation_audit.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    elif mutation == "duplicate_audit":
        rows = list(csv.DictReader((run / "translation_audit.csv").open("r", newline="", encoding="utf-8")))
        with (run / "translation_audit.csv").open("a", newline="", encoding="utf-8") as handle:
            csv.DictWriter(handle, fieldnames=AUDIT_FIELDS).writerow(rows[0])
        expectation = RunExpectation(**{**expectation.__dict__, "audit_rows": 2})
    elif mutation == "wrong_count":
        expectation = RunExpectation(**{**expectation.__dict__, "result_rows": 3})

    output = tmp_path / "publication"
    with pytest.raises(ValueError, match=message):
        export_publication_package([run], output, expectations={"retry-off": expectation})
    assert not output.exists()


def test_cli_parser_accepts_two_runs_and_output_directory() -> None:
    args = build_parser().parse_args(
        [
            "--retry-off",
            "off",
            "--retry-on",
            "on",
            "--output-dir",
            "reports/artifacts",
        ]
    )

    assert args.retry_off == Path("off")
    assert args.retry_on == Path("on")
    assert args.output_dir == Path("reports/artifacts")
