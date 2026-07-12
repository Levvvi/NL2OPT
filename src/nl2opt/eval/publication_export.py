"""Validate and export privacy-safe public benchmark artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


_TERMINAL_AUDIT_STATUSES = ("approved", "rejected", "waived")
_PRIVATE_PATTERNS = (
    re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    re.compile(r"\blevil\b", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_-]?key|password|secret)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class RunExpectation:
    checker_retry: str
    result_rows: int
    audit_rows: int
    strict_passes: int
    loose_passes: int
    audit_status_counts: Mapping[str, int]
    checker_retries: int


PUBLIC_EXPECTATIONS: dict[str, RunExpectation] = {
    "public-20260710-off": RunExpectation(
        checker_retry="off",
        result_rows=2070,
        audit_rows=105,
        strict_passes=1098,
        loose_passes=1098,
        audit_status_counts={"approved": 93, "rejected": 12, "waived": 0},
        checker_retries=0,
    ),
    "public-20260711-on-rerun": RunExpectation(
        checker_retry="on",
        result_rows=2070,
        audit_rows=105,
        strict_passes=1083,
        loose_passes=1083,
        audit_status_counts={"approved": 95, "rejected": 10, "waived": 0},
        checker_retries=412,
    ),
}


_PACKAGE_README = """# Audited public benchmark artifacts

This package is derived from the completed, manifest-pinned NL4Opt/IndustryOR
retry-off and independent retry-on benchmark runs. The formal tables,
limitations, and protocol interpretation remain in [`../bench_report.md`](../bench_report.md).

## Reproduction

Regenerate this directory from the local completed runs with:

```bash
python -m nl2opt.eval.publication_export \\
  --retry-off eval/results/public-20260710-off \\
  --retry-on eval/results/public-20260711-on-rerun \\
  --output-dir reports/artifacts
```

`manifest.json` records run-level counts and SHA-256 digests for every exported
source artifact. Each run directory contains the sanitized result CSV, completed
run manifest, and terminal translation audit.

## Sanitization and failure provenance

Absolute local failure paths are replaced by stable `failures/<filename>`
archive references. The complete failure JSON archives remain local because
they can contain implementation and machine context; the published result CSV
retains failure categories and stable archive references for traceability.
Credentials and local Windows user paths are rejected before any package file
is written.
"""


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            return fields, list(reader)
    except OSError as exc:
        raise ValueError(f"cannot read publication input: {path}") from exc


def _as_bool(value: str, *, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean value for {field}: {value!r}")


def _csv_bytes(fields: tuple[str, ...], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _assert_private_material_absent(data: bytes, *, source: str) -> None:
    text = data.decode("utf-8")
    if any(pattern.search(text) for pattern in _PRIVATE_PATTERNS):
        raise ValueError(f"credential-like or private path material found in {source}")


def _require_fields(fields: tuple[str, ...], required: set[str], *, label: str) -> None:
    missing = required - set(fields)
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(sorted(missing))}")


def _validate_and_serialize_run(
    run_dir: Path, expectation: RunExpectation
) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    results_fields, result_rows = _read_csv(run_dir / "results.csv")
    audit_fields, audit_rows = _read_csv(run_dir / "translation_audit.csv")
    _require_fields(
        results_fields,
        {
            "dataset",
            "item_id",
            "track",
            "repetition",
            "checker_retry",
            "passed_1e_6",
            "passed_1e_4",
            "checker_retried",
            "failure_artifact",
        },
        label="results CSV",
    )
    _require_fields(
        audit_fields,
        {"dataset", "item_id", "repetition", "numbers_match", "human_audit_status"},
        label="translation audit CSV",
    )
    try:
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read completed manifest for {run_dir}") from exc
    if not isinstance(manifest, dict) or not manifest.get("run_id") or not manifest.get("completed_at"):
        raise ValueError(f"publication requires a completed manifest for {run_dir}")
    run_id = str(manifest["run_id"])
    if run_id != run_dir.name:
        raise ValueError(f"run ID does not match input directory: {run_id!r}")
    if manifest.get("checker_retry") != expectation.checker_retry:
        raise ValueError(f"checker-retry mode mismatch for {run_id}")
    if len(result_rows) != expectation.result_rows:
        raise ValueError(
            f"result row count mismatch for {run_id}: {len(result_rows)} != {expectation.result_rows}"
        )
    if len(audit_rows) != expectation.audit_rows:
        raise ValueError(f"audit row count mismatch for {run_id}: {len(audit_rows)} != {expectation.audit_rows}")

    result_keys: set[tuple[str, str, str, int, str]] = set()
    strict_passes = loose_passes = checker_retries = 0
    sanitized_results: list[dict[str, str]] = []
    for row in result_rows:
        try:
            key = (
                row["dataset"],
                row["item_id"],
                row["track"],
                int(row["repetition"]),
                row["checker_retry"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid result key in {run_id}") from exc
        if key in result_keys:
            raise ValueError(f"duplicate result key in {run_id}: {key}")
        result_keys.add(key)
        if row["checker_retry"] != expectation.checker_retry:
            raise ValueError(f"checker-retry mode mismatch in result row for {run_id}")
        strict_passes += _as_bool(row["passed_1e_6"], field="passed_1e_6")
        loose_passes += _as_bool(row["passed_1e_4"], field="passed_1e_4")
        checker_retries += _as_bool(row["checker_retried"], field="checker_retried")
        sanitized = dict(row)
        artifact = row["failure_artifact"].strip()
        if artifact:
            filename = artifact.replace("\\", "/").rsplit("/", 1)[-1]
            if not filename or filename in {".", ".."}:
                raise ValueError(f"invalid failure artifact reference in {run_id}")
            sanitized["failure_artifact"] = f"failures/{filename}"
        sanitized_results.append(sanitized)
    if strict_passes != expectation.strict_passes or loose_passes != expectation.loose_passes:
        raise ValueError(f"pass count mismatch for {run_id}")
    if checker_retries != expectation.checker_retries:
        raise ValueError(f"checker retry count mismatch for {run_id}")

    audit_keys: set[tuple[str, str, int]] = set()
    audit_statuses: Counter[str] = Counter()
    for row in audit_rows:
        try:
            key = (row["dataset"], row["item_id"], int(row["repetition"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid audit key in {run_id}") from exc
        if key in audit_keys:
            raise ValueError(f"duplicate audit key in {run_id}: {key}")
        audit_keys.add(key)
        status = row["human_audit_status"].strip().lower()
        if status not in _TERMINAL_AUDIT_STATUSES:
            raise ValueError(f"translation audit status is not terminal in {run_id}: {status or 'blank'}")
        if not _as_bool(row["numbers_match"], field="numbers_match") and status != "rejected":
            raise ValueError(f"numeric audit mismatch is not rejected in {run_id}")
        audit_statuses[status] += 1
    actual_status_counts = {status: audit_statuses[status] for status in _TERMINAL_AUDIT_STATUSES}
    expected_status_counts = {
        status: int(expectation.audit_status_counts.get(status, 0)) for status in _TERMINAL_AUDIT_STATUSES
    }
    if actual_status_counts != expected_status_counts or sum(actual_status_counts.values()) != len(audit_rows):
        raise ValueError(f"audit status count mismatch for {run_id}")

    files = {
        "results.csv": _csv_bytes(results_fields, sanitized_results),
        "run_manifest.json": _json_bytes(manifest),
        "translation_audit.csv": _csv_bytes(audit_fields, audit_rows),
    }
    for filename, data in files.items():
        _assert_private_material_absent(data, source=f"{run_id}/{filename}")
    summary = {
        "run_id": run_id,
        "checker_retry": expectation.checker_retry,
        "result_rows": len(result_rows),
        "strict_passes": strict_passes,
        "strict_rate": strict_passes / len(result_rows),
        "loose_passes": loose_passes,
        "loose_rate": loose_passes / len(result_rows),
        "checker_retry_count": checker_retries,
        "audit_rows": len(audit_rows),
        "audit_status_counts": actual_status_counts,
        "files": {
            "results.csv": {"sha256": _sha256(files["results.csv"]), "row_count": len(result_rows)},
            "run_manifest.json": {"sha256": _sha256(files["run_manifest.json"])},
            "translation_audit.csv": {
                "sha256": _sha256(files["translation_audit.csv"]),
                "row_count": len(audit_rows),
            },
        },
    }
    return run_id, files, summary


def export_publication_package(
    run_dirs: Sequence[Path],
    output_dir: Path,
    *,
    expectations: Mapping[str, RunExpectation],
) -> Path:
    """Validate all runs, then write a deterministic sanitized package."""

    output_dir = Path(output_dir)
    prepared: list[tuple[str, dict[str, bytes], dict[str, Any]]] = []
    seen_run_ids: set[str] = set()
    for value in run_dirs:
        run_dir = Path(value)
        expectation = expectations.get(run_dir.name)
        if expectation is None:
            raise ValueError(f"no publication expectation for run {run_dir.name!r}")
        exported = _validate_and_serialize_run(run_dir, expectation)
        if exported[0] in seen_run_ids:
            raise ValueError(f"duplicate run ID in publication inputs: {exported[0]}")
        seen_run_ids.add(exported[0])
        prepared.append(exported)
    if seen_run_ids != set(expectations):
        raise ValueError("publication inputs do not match expected run IDs")

    readme_bytes = _PACKAGE_README.encode("utf-8")
    package_manifest = {
        "schema_version": 1,
        "runs": [summary for _, _, summary in prepared],
        "package_files": {"README.md": {"sha256": _sha256(readme_bytes)}},
    }
    manifest_bytes = _json_bytes(package_manifest)
    _assert_private_material_absent(readme_bytes, source="README.md")
    _assert_private_material_absent(manifest_bytes, source="manifest.json")

    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_parent))
    backup: Path | None = None
    try:
        for run_id, files, _summary in prepared:
            destination = staging / run_id
            destination.mkdir()
            for filename, data in files.items():
                (destination / filename).write_bytes(data)
        (staging / "README.md").write_bytes(readme_bytes)
        (staging / "manifest.json").write_bytes(manifest_bytes)

        if output_dir.exists() or output_dir.is_symlink():
            backup = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=output_parent))
            backup.rmdir()
            shutil.move(str(output_dir), str(backup))
        try:
            shutil.move(str(staging), str(output_dir))
        except BaseException:
            if backup is not None and backup.exists() and not output_dir.exists():
                shutil.move(str(backup), str(output_dir))
                backup = None
            raise
        if backup is not None:
            if backup.is_dir() and not backup.is_symlink():
                shutil.rmtree(backup)
            else:
                backup.unlink()
            backup = None
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not output_dir.exists():
            shutil.move(str(backup), str(output_dir))
    return output_dir / "manifest.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export sanitized audited benchmark artifacts.")
    parser.add_argument("--retry-off", type=Path, required=True)
    parser.add_argument("--retry-on", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    export_publication_package(
        [args.retry_off, args.retry_on],
        args.output_dir,
        expectations=PUBLIC_EXPECTATIONS,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
