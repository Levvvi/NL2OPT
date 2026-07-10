"""Render audited public-benchmark results from recorded runner artifacts.

The benchmark runner deliberately records rows rather than aggregate claims.
This module is the publication boundary: it computes all values from those
rows and will not create a public report until the sampled Chinese
translations have completed human review.
"""

from __future__ import annotations

import argparse
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
    "failure_category",
    "router_problem_type",
    "extractor_provider",
    "extractor_model",
    "translation_usage",
    "extractor_usage",
}
_REQUIRED_AUDIT_FIELDS = {"dataset", "item_id", "repetition", "numbers_match", "human_audit_status"}
_COMPLETE_AUDIT_STATUSES = {"approved", "rejected", "waived"}
_PUBLIC_AUDIT_FRACTION = 0.10
_PUBLIC_REPETITIONS = 3
_USAGE_TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")
_PUBLIC_PROTOCOL_NUMBERS = {
    "timeout_sec": 60,
    "tolerance": 1e-6,
    "temperature": 0.0,
}
_PUBLIC_DATASET_IDENTITY_FIELDS = ("sha256", "revision", "url", "license", "expected_nonblank_rows")


def summarize_token_usage(rows: list[dict[str, str]]) -> dict[str, int]:
    """Sum recorded translation and extraction token usage without external dependencies."""

    totals = {
        f"{kind}_{token_field}": 0
        for kind in ("translation", "extractor")
        for token_field in _USAGE_TOKEN_FIELDS
    }
    for row in rows:
        for kind in ("translation", "extractor"):
            try:
                usage = json.loads(row.get(f"{kind}_usage", ""))
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(usage, dict):
                continue
            for token_field in _USAGE_TOKEN_FIELDS:
                value = usage.get(token_field, 0)
                if isinstance(value, int) and not isinstance(value, bool):
                    totals[f"{kind}_{token_field}"] += value
    return totals


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


def _public_dataset_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    scope = manifest.get("dataset")
    scopes = {
        "all": ("nl4opt", "industryor"),
        "nl4opt": ("nl4opt",),
        "industryor": ("industryor",),
    }
    if scope not in scopes:
        raise ValueError("run manifest has an invalid public dataset scope")
    dataset_names = scopes[scope]
    if set(manifest["datasets"]) != set(dataset_names):
        raise ValueError("run manifest dataset entries do not match the requested public scope")
    return dataset_names


def _result_key(row: dict[str, str]) -> tuple[str, str, str, int, str]:
    try:
        repetition = int(row["repetition"])
    except ValueError as exc:
        raise ValueError(f"invalid repetition value: {row['repetition']!r}") from exc
    return (
        row["dataset"].strip().lower(),
        row["item_id"].strip(),
        row["track"].strip().lower(),
        repetition,
        row["checker_retry"].strip().lower(),
    )


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"run manifest field {field} must be a finite number")
    return float(value)


def _validate_public_protocol(manifest: dict[str, Any]) -> None:
    """Fail closed unless every immutable public-run setting is exact."""

    for field, expected in _PUBLIC_PROTOCOL_NUMBERS.items():
        actual = _finite_number(manifest.get(field), field=field)
        if actual != expected:
            raise ValueError(f"public reports require {field} == {expected}")
    if manifest.get("prompt_version") != "v4":
        raise ValueError("public reports require prompt_version == 'v4'")
    requested_model = manifest.get("requested_model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise ValueError("public reports require a non-empty requested_model")


def _dataset_identity(entry: Any, *, dataset: str) -> tuple[object, ...]:
    if not isinstance(entry, dict):
        raise ValueError(f"run manifest has an invalid dataset entry for {dataset}")
    values: list[object] = []
    for field in _PUBLIC_DATASET_IDENTITY_FIELDS:
        value = entry.get(field)
        if field == "expected_nonblank_rows":
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"run manifest has an invalid {field} for {dataset}")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError(f"run manifest has no {field} for {dataset}")
        values.append(value)
    return tuple(values)


def _actual_extractor_identities(result_rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    """Return every recorded provider/model pair without inventing a default."""

    identities: set[tuple[str, str]] = set()
    for row in result_rows:
        provider = row["extractor_provider"].strip()
        model = row["extractor_model"].strip()
        router_problem_type = row["router_problem_type"].strip().lower()
        status = row["status"].strip().upper()
        strict_passed = _as_bool(row["passed_1e_6"], field="passed_1e_6")
        failure_category = row["failure_category"].strip()
        if not strict_passed and not failure_category:
            raise ValueError("public reports require failure_category for every strict failure")
        if bool(provider) != bool(model):
            raise ValueError("actual extractor metadata must contain provider/model pairs")
        if provider:
            identities.add((provider, model))
            continue
        if router_problem_type == "unsupported" and status == "UNSUPPORTED":
            continue
        if router_problem_type:
            raise ValueError("actual extractor metadata is blank after extraction")
        raise ValueError("actual extractor metadata is blank without an explicit unsupported router result")
    if not identities:
        raise ValueError("public reports require non-empty actual extractor metadata")
    return identities


def _usage_summary_text(result_rows: list[dict[str, str]]) -> tuple[str, str]:
    """Render only recorded token totals; unavailable remains explicit."""

    totals = summarize_token_usage(result_rows)
    labels: list[str] = []
    for kind in ("translation", "extractor"):
        recorded = False
        for row in result_rows:
            try:
                usage = json.loads(row.get(f"{kind}_usage", ""))
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(usage, dict):
                recorded = True
                break
        if not recorded:
            labels.append(f"{kind} tokens unavailable (not recorded)")
            continue
        labels.append(
            f"{kind} total={totals[f'{kind}_total_tokens']} "
            f"(prompt={totals[f'{kind}_prompt_tokens']}, completion={totals[f'{kind}_completion_tokens']})"
        )
    return labels[0], labels[1]


def _recorded_time(manifest: dict[str, Any], field: str) -> str:
    value = manifest.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "unavailable (not recorded)"


def _validate_public_matrix(result_rows: list[dict[str, str]], manifest: dict[str, Any]) -> None:
    """Reject artifacts that are not a complete, standard public run."""

    _validate_public_protocol(manifest)
    try:
        audit_fraction = float(manifest["translation_audit_fraction"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("public reports require an audit fraction of exactly 0.10") from exc
    if audit_fraction != _PUBLIC_AUDIT_FRACTION:
        raise ValueError("public reports require an audit fraction of exactly 0.10")
    if "limit" not in manifest or manifest["limit"] is not None:
        raise ValueError("public reports reject any run with a limit")
    if manifest.get("track") != "all":
        raise ValueError("public reports require both en and zh tracks")
    if manifest.get("repetitions") != _PUBLIC_REPETITIONS:
        raise ValueError("public reports require exactly 3 repetitions")
    retry_mode = manifest.get("checker_retry")
    if retry_mode not in {"on", "off"}:
        raise ValueError("run manifest has an invalid checker-retry scope")

    dataset_names = _public_dataset_names(manifest)
    selected_item_ids = manifest.get("selected_item_ids")
    if not isinstance(selected_item_ids, dict) or set(selected_item_ids) != set(dataset_names):
        raise ValueError("run manifest has no complete selected-item scope for the public matrix")

    expected_keys: set[tuple[str, str, str, int, str]] = set()
    for dataset_name in dataset_names:
        entry = manifest["datasets"][dataset_name]
        _dataset_identity(entry, dataset=dataset_name)
        expected_count = entry["expected_nonblank_rows"]
        item_ids = selected_item_ids[dataset_name]
        if (
            not isinstance(item_ids, list)
            or not all(isinstance(item_id, str) and item_id for item_id in item_ids)
            or len(item_ids) != expected_count
            or len(set(item_ids)) != expected_count
        ):
            raise ValueError("public matrix scope does not contain every manifest item")
        for item_id in item_ids:
            for track in ("en", "zh"):
                for repetition in range(1, _PUBLIC_REPETITIONS + 1):
                    expected_keys.add((dataset_name, item_id, track, repetition, retry_mode))

    observed_keys: set[tuple[str, str, str, int, str]] = set()
    for row in result_rows:
        key = _result_key(row)
        if key in observed_keys:
            raise ValueError("public benchmark matrix contains a duplicate result key")
        observed_keys.add(key)
    if observed_keys != expected_keys:
        missing = expected_keys - observed_keys
        unexpected = observed_keys - expected_keys
        details = []
        if missing:
            details.append(f"missing {len(missing)} rows")
        if unexpected:
            details.append(f"unexpected {len(unexpected)} rows")
        raise ValueError(f"public benchmark matrix is incomplete or mismatched ({', '.join(details)})")


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
        key = (row["dataset"].strip().lower(), row["item_id"].strip(), repetition)
        if key in audited:
            raise ValueError("translation audit contains a duplicate translation audit key")
        audited.add(key)
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
    left_aligned = {"数据集", "语言轨道", "难度", "类型", "状态", "模式", "阈值"}
    separator = tuple("---" if header in left_aligned else "---:" for header in headers)
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def _dataset_references(manifest: dict[str, Any]) -> list[str]:
    lines = [
        "本报告未使用外部基准性能数值。未来如加入比较，必须在本节中列出原始来源、完全一致的评测协议和对应指标。",
        "",
    ]
    for dataset, entry in sorted(manifest["datasets"].items()):
        if not isinstance(entry, dict):
            continue
        url = entry.get("url", "source URL not recorded")
        revision = entry.get("revision", "revision not recorded")
        license_name = entry.get("license", "license not recorded")
        lines.append(f"- `{dataset}` 固定数据集来源：{url}（修订版 `{revision}`，许可证 `{license_name}`）。")
    return lines


def _load_validated_run(
    results_csv: Path,
    run_manifest: Path,
    audit_csv: Path,
) -> tuple[list[dict[str, str]], dict[str, Any], Counter[str]]:
    result_rows = _read_csv(Path(results_csv), _REQUIRED_RESULT_FIELDS, "benchmark results")
    manifest = _read_manifest(Path(run_manifest))
    audit_rows = _read_csv(Path(audit_csv), _REQUIRED_AUDIT_FIELDS, "translation audit")
    _validate_public_matrix(result_rows, manifest)
    _actual_extractor_identities(result_rows)
    audit_statuses = _audit_summary(audit_rows)
    _validate_audit_coverage(result_rows, audit_rows, manifest)
    return result_rows, manifest, audit_statuses


def _validate_retry_comparison_scope(
    primary_manifest: dict[str, Any],
    comparison_manifest: dict[str, Any],
    primary_rows: list[dict[str, str]],
    comparison_rows: list[dict[str, str]],
) -> None:
    if primary_manifest.get("checker_retry") != "off":
        raise ValueError("primary retry-ablation run must have checker_retry='off'")
    if comparison_manifest.get("checker_retry") != "on":
        raise ValueError("comparison retry-ablation run must have checker_retry='on'")
    if primary_manifest.get("dataset") != comparison_manifest.get("dataset"):
        raise ValueError("retry-ablation runs must use matching requested dataset scope")
    if primary_manifest["selected_item_ids"] != comparison_manifest["selected_item_ids"]:
        raise ValueError("retry-ablation runs must use matching selected item IDs")

    for field in (*_PUBLIC_PROTOCOL_NUMBERS, "prompt_version", "requested_model"):
        if primary_manifest.get(field) != comparison_manifest.get(field):
            raise ValueError(f"retry-ablation runs must use matching {field}")

    for dataset in _public_dataset_names(primary_manifest):
        primary_entry = primary_manifest["datasets"][dataset]
        comparison_entry = comparison_manifest["datasets"].get(dataset)
        primary_identity = _dataset_identity(primary_entry, dataset=dataset)
        comparison_identity = _dataset_identity(comparison_entry, dataset=dataset)
        if primary_identity != comparison_identity:
            if primary_identity[1] != comparison_identity[1]:
                raise ValueError("retry-ablation runs must use matching dataset revisions")
            raise ValueError("retry-ablation runs must use matching pinned dataset descriptors")

    if _actual_extractor_identities(primary_rows) != _actual_extractor_identities(comparison_rows):
        raise ValueError("retry-ablation runs must use matching actual extractor provider/model sets")


def _retry_summary_row(mode: str, rows: list[dict[str, str]]) -> tuple[str, str, str, str, str]:
    successes = _strict_successes(rows)
    rerun_count = sum(_as_bool(row["checker_retried"], field="checker_retried") for row in rows)
    return mode, str(successes), str(len(rows)), _rate(successes, len(rows)), str(rerun_count)


def render_benchmark_report(
    results_csv: Path,
    run_manifest: Path,
    audit_csv: Path,
    output: Path,
    *,
    comparison_results_csv: Path | None = None,
    comparison_run_manifest: Path | None = None,
    comparison_audit_csv: Path | None = None,
) -> Path:
    """Render an auditable Markdown report after a completed translation audit.

    All outcomes remain in denominators. The function writes ``output`` only
    after validating both the audit rows and the source artifacts, so callers
    cannot accidentally turn a pending translation sample into a public claim.
    """

    result_rows, manifest, audit_statuses = _load_validated_run(results_csv, run_manifest, audit_csv)
    comparison_paths = (comparison_results_csv, comparison_run_manifest, comparison_audit_csv)
    if any(path is not None for path in comparison_paths) and not all(path is not None for path in comparison_paths):
        raise ValueError("retry-ablation comparison requires results CSV, manifest, and audit artifacts")
    comparison_rows: list[dict[str, str]] | None = None
    if all(path is not None for path in comparison_paths):
        comparison_rows, comparison_manifest, _ = _load_validated_run(
            Path(comparison_results_csv),
            Path(comparison_run_manifest),
            Path(comparison_audit_csv),
        )
        _validate_retry_comparison_scope(manifest, comparison_manifest, result_rows, comparison_rows)

    strict_successes = _strict_successes(result_rows)
    loose_successes = _loose_successes(result_rows)
    total = len(result_rows)

    by_dataset_track: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_repetition: dict[int, list[dict[str, str]]] = defaultdict(list)
    by_industryor: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    failure_categories: Counter[str] = Counter()
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
        if dataset == "industryor":
            difficulty = _metadata_label(row, "difficulty", "difficulty_label", "unlabelled")
            problem_type = _metadata_label(row, "problem_type", "type", "unlabelled")
            by_industryor[(difficulty, problem_type)].append(row)
        if not _as_bool(row["passed_1e_6"], field="passed_1e_6"):
            failure_categories[row["failure_category"].strip()] += 1

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

    actual_extractor_identities = _actual_extractor_identities(result_rows)
    translation_usage_text, extractor_usage_text = _usage_summary_text(result_rows)
    failure_statuses = failure_categories

    audit_status_labels = {"approved": "已批准", "rejected": "已拒绝", "waived": "已豁免"}
    audit_summary_text = "，".join(
        f"{audit_status_labels[status]}：{count}" for status, count in sorted(audit_statuses.items())
    )
    retry_mode_labels = {"on": "开启", "off": "关闭"}
    if comparison_rows is None:
        primary_mode = str(manifest["checker_retry"])
        retry_rows = [_retry_summary_row(retry_mode_labels[primary_mode], result_rows)]
        retry_notice = "Checker 重试消融尚待完成：未提供配对的关闭和开启完整运行；不声明该消融已运行。"
    else:
        retry_rows = [
            _retry_summary_row(retry_mode_labels["off"], result_rows),
            _retry_summary_row(retry_mode_labels["on"], comparison_rows),
        ]
        retry_notice = "本表基于范围和数据集修订版均匹配的关闭与开启完整运行。"
    lines = [
        "# 公共基准测试报告",
        "",
        "## English executive summary",
        "",
        f"This audited public run contains {total} attempts from `{manifest.get('run_id', 'unknown')}`. "
        f"Strict 1e-6 success is {strict_successes}/{total} ({_rate(strict_successes, total)}); every outcome stays in the denominator.",
        "",
        "## 运行溯源",
        "",
        f"- Started: `{_recorded_time(manifest, 'started_at')}`",
        f"- Completed: `{_recorded_time(manifest, 'completed_at')}`",
        f"- Requested model: `{manifest['requested_model']}`",
        "- Actual extractor provider/model set: "
        + ", ".join(f"`{provider}/{model}`" for provider, model in sorted(actual_extractor_identities)),
        f"- Token totals: {translation_usage_text}; {extractor_usage_text}",
        "",
        "## 中文执行摘要",
        "",
        f"本次已审计公开运行包含 {total} 次尝试，严格 1e-6 通过数为 {strict_successes}/{total}"
        f"（{_rate(strict_successes, total)}）；所有结果均保留在分母中。",
        f"确定性的中文翻译抽样已完成：{audit_summary_text}。",
        "",
        "## 双轨结果",
        "",
        *_table(("数据集", "语言轨道", "尝试次数", "严格通过", "通过率"), dual_track_rows),
        "",
        "## 按重复次数的 Wilson 置信区间",
        "",
        *_table(("重复次数", "尝试次数", "严格通过", "通过率", "95% Wilson 区间"), repetition_rows),
        "",
        "## IndustryOR 类型/难度分解",
        "",
        "类型与难度只读取结果工件中记录的元数据；`unlabelled` 表示源工件没有提供该标签。",
        "",
        *_table(("难度", "类型", "尝试次数", "严格通过", "通过率"), industryor_rows),
        "",
        "## 失败分布",
        "",
        *_table(
            ("失败类型", "数量"),
            [(status, str(count)) for status, count in sorted(failure_statuses.items())] or [("无", "0")],
        ),
        "",
        "## 1e-4 敏感性",
        "",
        *_table(
            ("阈值", "成功数", "尝试次数", "通过率"),
            [
                ("严格 1e-6", str(strict_successes), str(total), _rate(strict_successes, total)),
                ("宽松 1e-4", str(loose_successes), str(total), _rate(loose_successes, total)),
            ],
        ),
        "",
        "## Checker 重试消融",
        "",
        retry_notice,
        "",
        *_table(("模式", "严格通过", "尝试次数", "通过率", "Checker 重跑次数"), retry_rows),
        "",
        "## 局限性",
        "",
        "1. 结果只适用于运行清单固定的数据集修订版、模型配置、超时和提示词版本，不能证明通用优化建模能力。",
        "2. 中文翻译质量只对确定性样本进行检查，而不是检查每一条翻译；审计待完成或阿拉伯数字不一致时，发布门禁会阻止生成报告。",
        "3. 目标值匹配和 checker 验证是必要条件，但不会使不受支持、非线性、随机性或其他不可表示的问题变得可解；这些结果仍计入失败分母。",
        "4. 只有同时记录配对的重试模式时，重试行才能描述配置消融；它们本身不能证明重试导致了差异。",
        "",
        "## 文献与数据集来源",
        "",
        *_dataset_references(manifest),
        "",
    ]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    """Build the report-rendering CLI parser without making benchmark calls."""

    parser = argparse.ArgumentParser(description="Render an audited NL2OPT benchmark report.")
    parser.add_argument("--results-csv", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison-results-csv", type=Path)
    parser.add_argument("--comparison-run-manifest", type=Path)
    parser.add_argument("--comparison-audit-csv", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = render_benchmark_report(
            args.results_csv,
            args.run_manifest,
            args.audit_csv,
            args.output,
            comparison_results_csv=args.comparison_results_csv,
            comparison_run_manifest=args.comparison_run_manifest,
            comparison_audit_csv=args.comparison_audit_csv,
        )
    except (ValueError, OSError) as exc:
        print(f"report rendering failed: {exc}")
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
