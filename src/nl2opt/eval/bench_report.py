"""Render audited public-benchmark results from recorded runner artifacts.

The benchmark runner deliberately records rows rather than aggregate claims.
This module is the publication boundary: it computes all values from those
rows and will not create a public report until the sampled Chinese
translations have completed human review.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_REQUIRED_RESULT_FIELDS = {
    "dataset",
    "item_id",
    "track",
    "repetition",
    "checker_retry",
    "status",
    "passed_1e_6",
    "passed_1e_4",
    "checker_retried",
}
_REQUIRED_AUDIT_FIELDS = {"dataset", "item_id", "repetition", "numbers_match", "human_audit_status"}
_COMPLETE_AUDIT_STATUSES = {"approved", "rejected", "waived"}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return a two-sided Wilson score interval, bounded to ``[0, 1]``."""

    if isinstance(successes, bool) or not isinstance(successes, int) or not 0 <= successes:
        raise ValueError("successes must be a non-negative integer")
    if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
        raise ValueError("total must be a positive integer")
    if successes > total:
        raise ValueError("successes cannot exceed total")
    if not isinstance(z, (int, float)) or isinstance(z, bool) or not math.isfinite(z) or z <= 0:
        raise ValueError("z must be a positive finite number")

    proportion = successes / total
    z_squared = z * z
    denominator = 1 + z_squared / total
    center = (proportion + z_squared / (2 * total)) / denominator
    half_width = z * math.sqrt(
        proportion * (1 - proportion) / total + z_squared / (4 * total * total)
    ) / denominator
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    if successes == 0:
        low = 0.0
    if successes == total:
        high = 1.0
    return low, high


def _read_csv(path: Path, required_fields: set[str], label: str) -> list[dict[str, str]]:
    try:
        with path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = set(reader.fieldnames or ())
            missing = sorted(required_fields - fieldnames)
            if missing:
                raise ValueError(f"{label} is missing required columns: {', '.join(missing)}")
            rows = list(reader)
    except FileNotFoundError as exc:
        raise ValueError(f"{label} is missing: {path}") from exc
    if not rows:
        raise ValueError(f"{label} has no rows")
    return rows


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"run manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"run manifest is invalid JSON: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("datasets"), dict):
        raise ValueError("run manifest must contain a datasets object")
    return payload


def _as_bool(value: str, *, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean value for {field}: {value!r}")


def _audit_summary(audit_rows: list[dict[str, str]]) -> Counter[str]:
    statuses: Counter[str] = Counter()
    for row in audit_rows:
        status = row["human_audit_status"].strip().lower()
        if status not in _COMPLETE_AUDIT_STATUSES:
            raise ValueError(f"translation audit is incomplete: {status or 'blank'} status")
        if not _as_bool(row["numbers_match"], field="numbers_match"):
            raise ValueError("translation audit contains an Arabic-number mismatch")
        statuses[status] += 1
    return statuses


def _validate_audit_coverage(
    result_rows: list[dict[str, str]], audit_rows: list[dict[str, str]], manifest: dict[str, Any]
) -> None:
    """Require the same deterministic Chinese sample selected by the runner."""

    try:
        fraction = float(manifest["translation_audit_fraction"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("run manifest has no valid translation audit fraction") from exc
    if not 0 < fraction <= 1:
        raise ValueError("run manifest has no valid translation audit fraction")

    chinese_rows = [row for row in result_rows if row["track"].strip().lower() == "zh"]
    if not chinese_rows:
        raise ValueError("translation audit cannot validate a report with no Chinese attempts")

    item_repetitions: dict[str, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    for row in chinese_rows:
        dataset = row["dataset"].strip().lower()
        item_id = row["item_id"].strip()
        try:
            repetition = int(row["repetition"])
        except ValueError as exc:
            raise ValueError(f"invalid repetition value: {row['repetition']!r}") from exc
        if not dataset or not item_id or repetition < 1:
            raise ValueError("benchmark results contain an invalid Chinese audit key")
        item_repetitions[dataset][item_id].add(repetition)

    expected: set[tuple[str, str, int]] = set()
    for dataset, repetitions_by_item in item_repetitions.items():
        sample_size = max(1, math.ceil(len(repetitions_by_item) * fraction))
        selected_items = sorted(
            repetitions_by_item,
            key=lambda item_id: hashlib.sha256(f"{dataset}:{item_id}".encode("utf-8")).hexdigest(),
        )[:sample_size]
        for item_id in selected_items:
            expected.update((dataset, item_id, repetition) for repetition in repetitions_by_item[item_id])

    audited: set[tuple[str, str, int]] = set()
    for row in audit_rows:
        try:
            repetition = int(row["repetition"])
        except ValueError as exc:
            raise ValueError(f"invalid translation audit repetition: {row['repetition']!r}") from exc
        audited.add((row["dataset"].strip().lower(), row["item_id"].strip(), repetition))
    missing = expected - audited
    if missing:
        formatted = ", ".join(f"{dataset}/{item_id}/r{repetition}" for dataset, item_id, repetition in sorted(missing))
        raise ValueError(f"translation audit is incomplete: missing deterministic sample rows ({formatted})")


def _rate(successes: int, total: int) -> str:
    return f"{(successes / total) if total else 0:.1%}"


def _strict_successes(rows: list[dict[str, str]]) -> int:
    return sum(_as_bool(row["passed_1e_6"], field="passed_1e_6") for row in rows)


def _loose_successes(rows: list[dict[str, str]]) -> int:
    return sum(_as_bool(row["passed_1e_4"], field="passed_1e_4") for row in rows)


def _metadata_label(row: dict[str, str], primary: str, alternate: str, default: str) -> str:
    return (row.get(primary) or row.get(alternate) or default).strip() or default


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    left_aligned = {"Dataset", "Track", "Difficulty", "Type", "Status", "Mode"}
    separator = tuple("---" if header in left_aligned else "---:" for header in headers)
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _dataset_references(manifest: dict[str, Any]) -> list[str]:
    lines = [
        "No external benchmark performance value is used in this report. Any future comparison must cite the "
        "primary source, the exact protocol, and the matching metric in this separate section.",
        "",
    ]
    for dataset, entry in sorted(manifest["datasets"].items()):
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "source URL not recorded")
        revision = entry.get("revision", "revision not recorded")
        license_name = entry.get("license", "license not recorded")
        lines.append(f"- `{dataset}` pinned dataset source: {url} (revision `{revision}`, license `{license_name}`).")
    return lines


def render_benchmark_report(results_csv: Path, run_manifest: Path, audit_csv: Path, output: Path) -> Path:
    """Render an auditable Markdown report after a completed translation audit.

    All outcomes remain in denominators. The function writes ``output`` only
    after validating both the audit rows and the source artifacts, so callers
    cannot accidentally turn a pending translation sample into a public claim.
    """

    result_rows = _read_csv(Path(results_csv), _REQUIRED_RESULT_FIELDS, "benchmark results")
    manifest = _read_manifest(Path(run_manifest))
    audit_rows = _read_csv(Path(audit_csv), _REQUIRED_AUDIT_FIELDS, "translation audit")
    audit_statuses = _audit_summary(audit_rows)
    _validate_audit_coverage(result_rows, audit_rows, manifest)

    strict_successes = _strict_successes(result_rows)
    loose_successes = _loose_successes(result_rows)
    total = len(result_rows)

    by_dataset_track: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_repetition: dict[int, list[dict[str, str]]] = defaultdict(list)
    by_industryor: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_retry_mode: dict[str, list[dict[str, str]]] = defaultdict(list)
    failure_statuses: Counter[str] = Counter()
    for row in result_rows:
        dataset = row["dataset"].strip().lower() or "unlabelled"
        track = row["track"].strip().lower() or "unlabelled"
        by_dataset_track[(dataset, track)].append(row)
        try:
            repetition = int(row["repetition"])
        except ValueError as exc:
            raise ValueError(f"invalid repetition value: {row['repetition']!r}") from exc
        if repetition < 1:
            raise ValueError(f"invalid repetition value: {row['repetition']!r}")
        by_repetition[repetition].append(row)
        retry_mode = row["checker_retry"].strip().lower() or "unlabelled"
        by_retry_mode[retry_mode].append(row)
        if dataset == "industryor":
            difficulty = _metadata_label(row, "difficulty", "difficulty_label", "unlabelled")
            problem_type = _metadata_label(row, "problem_type", "type", "unlabelled")
            by_industryor[(difficulty, problem_type)].append(row)
        if not _as_bool(row["passed_1e_6"], field="passed_1e_6"):
            failure_statuses[row["status"].strip() or "unlabelled"] += 1

    dual_track_rows = []
    for (dataset, track), rows in sorted(by_dataset_track.items()):
        successes = _strict_successes(rows)
        dual_track_rows.append((dataset, track, str(len(rows)), str(successes), _rate(successes, len(rows))))

    repetition_rows = []
    for repetition, rows in sorted(by_repetition.items()):
        successes = _strict_successes(rows)
        low, high = wilson_interval(successes, len(rows))
        repetition_rows.append(
            (str(repetition), str(len(rows)), str(successes), _rate(successes, len(rows)), f"[{low:.1%}, {high:.1%}]")
        )

    industryor_rows = []
    for (difficulty, problem_type), rows in sorted(by_industryor.items()):
        successes = _strict_successes(rows)
        industryor_rows.append((difficulty, problem_type, str(len(rows)), str(successes), _rate(successes, len(rows))))
    if not industryor_rows:
        industryor_rows.append(("not present", "not present", "0", "0", "0.0%"))

    retry_rows = []
    for mode, rows in sorted(by_retry_mode.items()):
        successes = _strict_successes(rows)
        rerun_count = sum(_as_bool(row["checker_retried"], field="checker_retried") for row in rows)
        retry_rows.append((mode, str(successes), str(len(rows)), _rate(successes, len(rows)), str(rerun_count)))

    audit_summary_text = ", ".join(f"{status}: {count}" for status, count in sorted(audit_statuses.items()))
    lines = [
        "# Public Benchmark Report",
        "",
        "## Executive summary",
        "",
        f"This audited report summarizes {total} recorded attempts from run `{manifest.get('run_id', 'unknown')}`. "
        f"The strict 1e-6 result is {strict_successes}/{total} ({_rate(strict_successes, total)}); all outcomes remain in the denominator.",
        f"The deterministic Chinese translation sample is complete ({audit_summary_text}).",
        "",
        "## 中文结果摘要",
        "",
        f"本报告基于已完成的人工翻译审计，汇总 {total} 次记录尝试。严格 1e-6 通过数为 "
        f"{strict_successes}/{total}（{_rate(strict_successes, total)}）；所有失败均保留在分母中。",
        "",
        "## Dual-track results",
        "",
        *_table(("Dataset", "Track", "Attempts", "Strict pass", "Rate"), dual_track_rows),
        "",
        "## Per-repetition Wilson intervals",
        "",
        *_table(("Repetition", "Attempts", "Strict pass", "Rate", "95% Wilson interval"), repetition_rows),
        "",
        "## IndustryOR type/difficulty decomposition",
        "",
        "Type and difficulty are read only from recorded result metadata; `unlabelled` means the source artifact did not provide that label.",
        "",
        *_table(("Difficulty", "Type", "Attempts", "Strict pass", "Rate"), industryor_rows),
        "",
        "## Failure distribution",
        "",
        *_table(
            ("Status", "Count"),
            [(status, str(count)) for status, count in sorted(failure_statuses.items())] or [("none", "0")],
        ),
        "",
        "## 1e-4 sensitivity",
        "",
        *_table(
            ("Threshold", "Successes", "Attempts", "Rate"),
            [
                ("strict 1e-6", str(strict_successes), str(total), _rate(strict_successes, total)),
                ("loose 1e-4", str(loose_successes), str(total), _rate(loose_successes, total)),
            ],
        ),
        "",
        "## Checker-retry ablation",
        "",
        "This table is descriptive. It compares only retry modes present in the supplied CSV and makes no causal claim when a matched mode is absent.",
        "",
        *_table(("Mode", "Strict pass", "Attempts", "Rate", "Checker reruns"), retry_rows),
        "",
        "## Limitations",
        "",
        "1. Results apply only to the manifest-pinned dataset revisions, model configuration, timeout, and prompt version recorded by the run; they do not establish general optimization-modeling ability.",
        "2. Chinese translation quality is checked on a deterministic sample, not every translation; the audit gate prevents publication while that sample is pending or has Arabic-number mismatches.",
        "3. Objective matching and checker verification are necessary but do not make unsupported, nonlinear, stochastic, or otherwise unrepresentable source problems solvable; such outcomes remain failures in the denominator.",
        "4. Checker-retry rows can describe a configured ablation only when both matched retry modes are recorded; they cannot by themselves prove that retry caused a difference.",
        "",
        "## Literature and dataset references",
        "",
        *_dataset_references(manifest),
        "",
    ]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
