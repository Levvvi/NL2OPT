"""Pinned public-benchmark loading and resumable execution helpers.

The runner intentionally records attempts rather than aggregate metrics.  A
later reporting step can therefore audit every denominator and failure without
re-running an API-backed benchmark.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, TypeVar

from nl2opt.agents.extractor import extract_problem_spec
from nl2opt.agents.llm_client import DeepSeekClient, LLMClient, LLMResponse
from nl2opt.agents.router import route_text
from nl2opt.pipeline import check_result_for_spec, run_problem_spec
from nl2opt.runtime.runner import load_solver_result


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASETS_DIR = PROJECT_ROOT / "eval" / "datasets"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "eval" / "results"
MANIFEST_FILENAME = "manifest.json"
TRANSPORT_BACKOFF_SECONDS = (2, 4, 8, 16, 32)
DEFAULT_TOLERANCE = 1e-6
LOOSE_TOLERANCE = 1e-4

# Kept in source (rather than improvised per request) so every Chinese attempt
# receives the same domain vocabulary instruction.
TRANSLATION_TERMINOLOGY: dict[str, str] = {
    "linear programming": "线性规划",
    "integer programming": "整数规划",
    "objective": "目标函数",
    "constraint": "约束",
    "maximize": "最大化",
    "minimize": "最小化",
    "subject to": "满足以下约束",
    "feasible": "可行",
    "infeasible": "不可行",
    "decision variable": "决策变量",
}

_NUMBER_TOKEN_RE = re.compile(r"(?<![A-Za-z_])[+-]?\d+(?:,\d{3})*(?:\.\d+)?")
_RESULT_FIELDS = (
    "dataset",
    "item_id",
    "difficulty",
    "problem_type",
    "track",
    "repetition",
    "checker_retry",
    "status",
    "checker_passed",
    "ground_truth",
    "objective_value",
    "passed_1e_6",
    "passed_1e_4",
    "judgment_reason",
    "translation_provider",
    "translation_model",
    "translation_usage",
    "translation_numbers_match",
    "api_attempts",
    "checker_retried",
    "failure_category",
    "router_problem_type",
    "extractor_provider",
    "extractor_model",
    "wall_sec",
    "evaluated_at",
    "error",
    "failure_artifact",
)
_AUDIT_FIELDS = (
    "dataset",
    "item_id",
    "repetition",
    "source_text",
    "translated_text",
    "source_number_tokens",
    "translated_number_tokens",
    "numbers_match",
    "translation_model",
    "translation_usage",
    "human_audit_status",
    "human_audit_notes",
)


@dataclass(frozen=True)
class BenchmarkItem:
    """One JSONL input and the objective/status used as its public answer."""

    dataset: str
    item_id: str
    question: str
    ground_truth: Any
    raw: dict[str, Any]


@dataclass(frozen=True)
class BenchmarkJudgment:
    """Objective judgment under the two pre-registered tolerances."""

    passed_1e_6: bool
    passed_1e_4: bool
    reason: str
    expected_value: float | None = None
    actual_value: float | None = None
    infeasibility_accepted: bool = False

    @property
    def at_1e_6(self) -> bool:
        return self.passed_1e_6

    @property
    def at_1e_4(self) -> bool:
        return self.passed_1e_4

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed_1e_6": self.passed_1e_6,
            "passed_1e_4": self.passed_1e_4,
            "at_1e_6": self.passed_1e_6,
            "at_1e_4": self.passed_1e_4,
            "reason": self.reason,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "infeasibility_accepted": self.infeasibility_accepted,
        }


@dataclass
class BenchmarkAttempt:
    """The minimal, serialisable outcome of one extraction-and-solve attempt."""

    status: str
    objective_value: float | None = None
    checker_passed: bool = False
    spec: Any | None = None
    solver_result: Any | None = None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TranslationResult:
    translated_text: str | None
    provider: str | None
    model: str | None
    usage: dict[str, Any] | None
    source_numbers: tuple[str, ...]
    translated_numbers: tuple[str, ...]
    numbers_match: bool
    api_attempts: int
    error: str | None = None


AttemptRunner = Callable[[BenchmarkItem, str, int, "BenchmarkRunConfig"], BenchmarkAttempt]
CheckerRetryRunner = Callable[[BenchmarkAttempt], bool]


@dataclass
class BenchmarkRunConfig:
    """Inputs that make a benchmark run reproducible and resumable."""

    datasets_dir: Path = DEFAULT_DATASETS_DIR
    results_dir: Path = DEFAULT_RESULTS_DIR
    results_csv: Path | None = None
    dataset: str = "all"
    track: str = "all"
    repetitions: int = 3
    checker_retry: bool = False
    resume: bool = False
    limit: int | None = None
    timeout_sec: int = 60
    run_id: str = "benchmark"
    tolerance: float = DEFAULT_TOLERANCE
    client: LLMClient | None = None
    attempt_runner: AttemptRunner | None = None
    checker_retry_runner: CheckerRetryRunner | None = None
    sleep: Callable[[float], None] = time.sleep
    audit_fraction: float = 0.10

    def __post_init__(self) -> None:
        self.datasets_dir = Path(self.datasets_dir)
        self.results_dir = Path(self.results_dir)
        if self.results_csv is not None:
            self.results_csv = Path(self.results_csv)
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be at least 1 when provided")
        if self.timeout_sec < 1:
            raise ValueError("timeout_sec must be at least 1")
        if self.tolerance <= 0:
            raise ValueError("tolerance must be positive")
        if not 0 < self.audit_fraction <= 1:
            raise ValueError("audit_fraction must be in (0, 1]")


class _JsonClient(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> LLMResponse:
        ...


T = TypeVar("T")


def _canonical_dataset_name(name: str) -> str:
    normalized = name.strip().lower()
    aliases = {
        "nl4opt": "nl4opt",
        "nl4opt_fixed": "nl4opt",
        "industryor": "industryor",
        "industryor_fixedv2": "industryor",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown benchmark dataset: {name}") from exc


def _load_manifest(datasets_dir: Path) -> dict[str, Any]:
    path = Path(datasets_dir) / MANIFEST_FILENAME
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"benchmark manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"benchmark manifest is invalid JSON: {path}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("datasets"), dict):
        raise ValueError("benchmark manifest must contain a datasets object")
    return manifest


def _dataset_entry(name: str, datasets_dir: Path) -> tuple[str, dict[str, Any]]:
    canonical_name = _canonical_dataset_name(name)
    manifest = _load_manifest(datasets_dir)
    entry = manifest["datasets"].get(canonical_name)
    if not isinstance(entry, dict):
        raise ValueError(f"benchmark manifest has no entry for {canonical_name}")
    required = ("upstream_filename", "local_filename", "revision", "url", "sha256", "license", "expected_nonblank_rows")
    missing = [field_name for field_name in required if field_name not in entry]
    if missing:
        raise ValueError(f"benchmark manifest entry for {canonical_name} is missing {', '.join(missing)}")
    return canonical_name, entry


def _item_value(raw: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in raw and raw[name] is not None:
            return raw[name]
    return None


def load_benchmark_dataset(name: str, datasets_dir: Path) -> list[BenchmarkItem]:
    """Load a pinned JSONL dataset only after its bytes and row count verify."""

    datasets_dir = Path(datasets_dir)
    canonical_name, entry = _dataset_entry(name, datasets_dir)
    path = datasets_dir / str(entry["local_filename"])
    try:
        payload = path.read_bytes()
    except FileNotFoundError as exc:
        raise ValueError(f"pinned dataset is missing: {path}") from exc

    actual_hash = hashlib.sha256(payload).hexdigest()
    expected_hash = str(entry["sha256"]).lower()
    if actual_hash != expected_hash:
        raise ValueError(
            f"sha256 mismatch for {canonical_name}: expected {expected_hash}, got {actual_hash}"
        )

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"pinned dataset is not valid UTF-8: {path}") from exc
    nonblank_rows = [line for line in text.splitlines() if line.strip()]
    expected_count = int(entry["expected_nonblank_rows"])
    if len(nonblank_rows) != expected_count:
        raise ValueError(
            f"row count mismatch for {canonical_name}: expected {expected_count}, got {len(nonblank_rows)}"
        )

    items: list[BenchmarkItem] = []
    for position, line in enumerate(nonblank_rows, start=1):
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL row {position} in {path}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"JSONL row {position} in {path} is not an object")
        question = _item_value(raw, ("en_question", "question", "problem", "input", "prompt"))
        ground_truth = _item_value(raw, ("en_answer", "answer", "objective_value", "objective", "solution"))
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"JSONL row {position} in {path} has no text question")
        item_id = _item_value(raw, ("id", "item_id", "case_id"))
        items.append(
            BenchmarkItem(
                dataset=canonical_name,
                item_id=str(item_id) if item_id is not None else f"{canonical_name}-{position:04d}",
                question=question,
                ground_truth=ground_truth,
                raw=raw,
            )
        )
    return items


def _status_from_prediction(prediction: Any) -> str | None:
    if isinstance(prediction, Mapping):
        value = prediction.get("status", prediction.get("solver_status"))
    else:
        value = getattr(prediction, "status", getattr(prediction, "solver_status", None))
    if value is None:
        return None
    return getattr(value, "value", str(value)).upper()


def _objective_from_prediction(prediction: Any) -> float | None:
    if isinstance(prediction, Mapping):
        value = prediction.get("objective_value", prediction.get("objective"))
    elif isinstance(prediction, (float, int)) and not isinstance(prediction, bool):
        value = prediction
    else:
        value = getattr(prediction, "objective_value", getattr(prediction, "objective", None))
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _ground_truth_is_infeasible(ground_truth: Any) -> bool:
    if isinstance(ground_truth, Mapping):
        ground_truth = ground_truth.get("status", ground_truth.get("answer"))
    return isinstance(ground_truth, str) and ground_truth.strip().upper() == "INFEASIBLE"


def _numeric_ground_truth(ground_truth: Any) -> float | None:
    if isinstance(ground_truth, Mapping):
        ground_truth = ground_truth.get("objective_value", ground_truth.get("answer", ground_truth.get("objective")))
    try:
        value = float(ground_truth)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def judge_benchmark_result(
    prediction: Any,
    ground_truth: Any,
    spec: Any,
    checker_passed: bool,
    tolerance: float,
) -> BenchmarkJudgment:
    """Judge a checker-verified prediction at 1e-6 and 1e-4.

    ``spec`` is deliberately accepted here even though objective comparison is
    dataset-level: it records that the answer came from the extracted model and
    leaves room for future family-specific judging without changing the runner
    interface.
    """

    del spec
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    status = _status_from_prediction(prediction)
    if _ground_truth_is_infeasible(ground_truth):
        accepted = status == "INFEASIBLE" and bool(checker_passed)
        reason = "verified_infeasible" if accepted else "infeasible_requires_verified_checker"
        return BenchmarkJudgment(accepted, accepted, reason, infeasibility_accepted=accepted)

    expected = _numeric_ground_truth(ground_truth)
    actual = _objective_from_prediction(prediction)
    if not checker_passed:
        return BenchmarkJudgment(False, False, "checker_failed", expected, actual)
    if expected is None:
        return BenchmarkJudgment(False, False, "invalid_ground_truth", expected, actual)
    if actual is None:
        return BenchmarkJudgment(False, False, "missing_numeric_objective", expected, actual)
    if status == "INFEASIBLE":
        return BenchmarkJudgment(False, False, "unexpected_infeasible", expected, actual)

    error = abs(actual - expected)
    strict_tolerance = tolerance
    return BenchmarkJudgment(
        passed_1e_6=error <= strict_tolerance,
        passed_1e_4=error <= LOOSE_TOLERANCE,
        reason="objective_match" if error <= strict_tolerance else "objective_mismatch",
        expected_value=expected,
        actual_value=actual,
    )


def _is_transport_failure(exc: Exception) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return any(token in name or token in message for token in ("connection", "transport", "timeout"))


def call_with_transport_retry(
    operation: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry transport failures after 2, 4, 8, 16 and 32 seconds."""

    for attempt_number in range(len(TRANSPORT_BACKOFF_SECONDS) + 1):
        try:
            return operation()
        except Exception as exc:
            if not _is_transport_failure(exc) or attempt_number == len(TRANSPORT_BACKOFF_SECONDS):
                raise
            sleep(TRANSPORT_BACKOFF_SECONDS[attempt_number])
    raise AssertionError("unreachable")


class _RetryingJsonClient:
    """Apply the benchmark transport policy to extraction calls as well."""

    def __init__(self, client: _JsonClient, sleep: Callable[[float], None]) -> None:
        self._client = client
        self._sleep = sleep

    def complete_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> LLMResponse:
        return call_with_transport_retry(
            lambda: self._client.complete_json(system_prompt, user_prompt, temperature=temperature),
            sleep=self._sleep,
        )


def _number_tokens(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).replace(",", "") for match in _NUMBER_TOKEN_RE.finditer(text))


def _translation_system_prompt() -> str:
    terminology = "\n".join(f"- {source} => {target}" for source, target in TRANSLATION_TERMINOLOGY.items())
    return (
        "Translate the user text from English to simplified Chinese for an optimization-model "
        "extraction benchmark. Preserve every Arabic-number token and all mathematical symbols. "
        "Use this fixed terminology map when applicable:\n"
        f"{terminology}\n"
        "Return exactly one JSON object with a string field named translation."
    )


def translate_to_chinese(
    source_text: str,
    client: _JsonClient,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> TranslationResult:
    """Translate once, recording model/usage and enforcing numeric preservation."""

    attempts = 0

    def request() -> LLMResponse:
        nonlocal attempts
        attempts += 1
        return client.complete_json(_translation_system_prompt(), source_text, temperature=0.0)

    source_numbers = _number_tokens(source_text)
    try:
        response = call_with_transport_retry(request, sleep=sleep)
        payload = json.loads(response.content)
        translated_text = payload.get("translation") if isinstance(payload, dict) else None
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError("translation response has no non-empty translation field")
        translated_numbers = _number_tokens(translated_text)
        return TranslationResult(
            translated_text=translated_text,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            source_numbers=source_numbers,
            translated_numbers=translated_numbers,
            numbers_match=source_numbers == translated_numbers,
            api_attempts=attempts,
        )
    except Exception as exc:
        return TranslationResult(
            translated_text=None,
            provider=None,
            model=None,
            usage=None,
            source_numbers=source_numbers,
            translated_numbers=(),
            numbers_match=False,
            api_attempts=attempts,
            error=str(exc),
        )


def _run_default_attempt(
    item: BenchmarkItem,
    text: str,
    repetition: int,
    config: BenchmarkRunConfig,
    client: LLMClient,
    output_dir: Path,
) -> BenchmarkAttempt:
    del item, repetition
    route_details: dict[str, Any] = {}
    try:
        route = route_text(text)
        route_details = {
            "router_problem_type": route.problem_type.value,
            "router_reason": route.reason,
        }
        if route.problem_type.value == "unsupported":
            return BenchmarkAttempt(
                status="UNSUPPORTED",
                error=route.reason,
                details=route_details,
            )
        extraction = extract_problem_spec(
            text,
            problem_type=route.problem_type,
            client=_RetryingJsonClient(client, config.sleep),
            prompt_version="v4",
        )
        extraction_details = {
            **route_details,
            "extractor_provider": extraction.provider or "",
            "extractor_model": extraction.model or "",
        }
        if not extraction.success or extraction.spec is None:
            status = "API_ERROR" if _error_is_transport_or_client(extraction.error) else "EXTRACTION_ERROR"
            return BenchmarkAttempt(
                status=status,
                error=extraction.error or "extraction failed",
                details=extraction_details,
            )
        spec = extraction.spec
        if getattr(spec, "problem_type", None) == "unsupported":
            return BenchmarkAttempt(
                status="UNSUPPORTED",
                spec=spec,
                error=getattr(spec, "reason", "unsupported"),
                details=extraction_details,
            )
        pipeline_result = run_problem_spec(spec, output_dir, timeout_sec=config.timeout_sec)
        solver_result = None
        if pipeline_result.solution_path:
            solution_path = Path(pipeline_result.solution_path)
            if solution_path.exists():
                solver_result = load_solver_result(solution_path)
        return BenchmarkAttempt(
            status=pipeline_result.solver_status or ("TIMEOUT" if pipeline_result.timed_out else "ERROR"),
            objective_value=pipeline_result.objective_value,
            checker_passed=pipeline_result.checker_passed,
            spec=spec,
            solver_result=solver_result,
            error=pipeline_result.error,
            details={
                **extraction_details,
                "runtime_sec": pipeline_result.runtime_sec,
                "violations": pipeline_result.violations,
                "returncode": pipeline_result.returncode,
                "work_dir": str(output_dir),
            },
        )
    except Exception as exc:
        return BenchmarkAttempt(
            status="API_ERROR" if _is_transport_failure(exc) else "ERROR",
            error=str(exc),
            details=route_details,
        )


def _normalise_attempt(value: Any) -> BenchmarkAttempt:
    if isinstance(value, BenchmarkAttempt):
        return value
    if isinstance(value, Mapping):
        return BenchmarkAttempt(
            status=str(value.get("status", value.get("solver_status", "ERROR"))),
            objective_value=_objective_from_prediction(value),
            checker_passed=bool(value.get("checker_passed", False)),
            spec=value.get("spec"),
            solver_result=value.get("solver_result"),
            error=value.get("error"),
            details=dict(value.get("details", {})),
        )
    return BenchmarkAttempt(
        status=_status_from_prediction(value) or "ERROR",
        objective_value=_objective_from_prediction(value),
        checker_passed=bool(getattr(value, "checker_passed", False)),
        spec=getattr(value, "spec", None),
        solver_result=getattr(value, "solver_result", None),
        error=getattr(value, "error", None),
    )


def _retry_checker(attempt: BenchmarkAttempt, config: BenchmarkRunConfig) -> tuple[BenchmarkAttempt, bool]:
    if not config.checker_retry or attempt.checker_passed:
        return attempt, False
    try:
        if config.checker_retry_runner is not None:
            checker_passed = bool(config.checker_retry_runner(attempt))
        elif attempt.spec is not None and attempt.solver_result is not None:
            checker_passed = bool(check_result_for_spec(attempt.spec, attempt.solver_result).passed)
        else:
            return attempt, False
    except Exception as exc:
        details = {**attempt.details, "checker_retry_error": str(exc)}
        return BenchmarkAttempt(
            status=attempt.status,
            objective_value=attempt.objective_value,
            checker_passed=False,
            spec=attempt.spec,
            solver_result=attempt.solver_result,
            error=attempt.error or str(exc),
            details=details,
        ), True
    return BenchmarkAttempt(
        status=attempt.status,
        objective_value=attempt.objective_value,
        checker_passed=checker_passed,
        spec=attempt.spec,
        solver_result=attempt.solver_result,
        error=attempt.error,
        details=attempt.details,
    ), True


def _resolve_output_paths(config: BenchmarkRunConfig) -> tuple[Path, Path, Path]:
    results_csv = config.results_csv or (config.results_dir / config.run_id / "results.csv")
    output_dir = results_csv.parent
    return results_csv, output_dir / "translation_audit.csv", output_dir / "run_manifest.json"


def _selected_dataset_names(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("nl4opt", "industryor")
    return (_canonical_dataset_name(value),)


def _selected_tracks(value: str) -> tuple[str, ...]:
    if value == "all":
        return ("en", "zh")
    if value not in {"en", "zh"}:
        raise ValueError("track must be one of all, en, zh")
    return (value,)


def _resume_keys(results_csv: Path) -> set[tuple[str, str, str, int, str]]:
    if not results_csv.exists() or results_csv.stat().st_size == 0:
        return set()
    with results_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            (
                row["dataset"],
                row["item_id"],
                row["track"],
                int(row["repetition"]),
                row["checker_retry"],
            )
            for row in reader
        }


def _validate_results_header(results_csv: Path) -> None:
    if not results_csv.exists() or results_csv.stat().st_size == 0:
        return
    with results_csv.open("r", newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle), None)
    if tuple(header or ()) != _RESULT_FIELDS:
        raise ValueError("results CSV header is incompatible with the current telemetry schema")


def _audit_item_keys(items: list[BenchmarkItem], fraction: float) -> set[tuple[str, str]]:
    by_dataset: dict[str, list[BenchmarkItem]] = {}
    for item in items:
        by_dataset.setdefault(item.dataset, []).append(item)
    selected: set[tuple[str, str]] = set()
    for dataset, dataset_items in by_dataset.items():
        count = max(1, math.ceil(len(dataset_items) * fraction)) if dataset_items else 0
        ranked = sorted(
            dataset_items,
            key=lambda item: hashlib.sha256(f"{dataset}:{item.item_id}".encode("utf-8")).hexdigest(),
        )
        selected.update((item.dataset, item.item_id) for item in ranked[:count])
    return selected


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value is not None else ""


def _attempt_payload(attempt: BenchmarkAttempt) -> dict[str, Any]:
    def serializable(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if is_dataclass(value):
            return asdict(value)
        return value

    return {
        "status": attempt.status,
        "objective_value": attempt.objective_value,
        "checker_passed": attempt.checker_passed,
        "spec": serializable(attempt.spec),
        "solver_result": serializable(attempt.solver_result),
        "error": attempt.error,
        "details": attempt.details,
    }


def _attempt_work_dir(attempt: BenchmarkAttempt | None) -> Path | None:
    if attempt is None:
        return None
    value = attempt.details.get("work_dir")
    if not isinstance(value, str):
        return None
    return Path(value)


def _attempt_problem_type(attempt: BenchmarkAttempt | None) -> str:
    """Return extracted type metadata for later reporting without judging it."""

    if attempt is None or attempt.spec is None:
        return ""
    if isinstance(attempt.spec, Mapping):
        value = attempt.spec.get("problem_type", "")
    else:
        value = getattr(attempt.spec, "problem_type", "")
    return str(getattr(value, "value", value)) if value is not None else ""


def _attempt_detail(attempt: BenchmarkAttempt | None, key: str) -> str:
    if attempt is None:
        return ""
    value = attempt.details.get(key, "")
    return str(value) if value is not None else ""


def _error_is_transport_or_client(error: str | None) -> bool:
    if not error:
        return False
    normalized = error.lower()
    return any(
        signal in normalized
        for signal in (
            "llm client",
            "api key",
            "api error",
            "connection",
            "transport",
            "rate limit",
            "request timeout",
        )
    )


def _failure_category(
    *,
    status: str,
    error: str | None,
    attempt: BenchmarkAttempt | None,
    judgment: BenchmarkJudgment | None,
) -> str:
    if judgment is not None and judgment.passed_1e_6:
        return ""

    normalized_status = status.upper()
    router_problem_type = _attempt_detail(attempt, "router_problem_type").lower()
    if normalized_status == "UNSUPPORTED" or router_problem_type == "unsupported" or _attempt_problem_type(attempt) == "unsupported":
        return "UNSUPPORTED"
    if normalized_status in {"TIMEOUT", "SOLVE_TIMEOUT"}:
        return "SOLVE_TIMEOUT"
    if normalized_status in {"API_ERROR", "API_ERR"} or _error_is_transport_or_client(error):
        return "API_ERR"
    if normalized_status in {"EXTRACTION_ERROR", "TRANSLATION_ERROR", "TRANSLATION_NUMBER_MISMATCH"}:
        return "EXTRACT_ERR"
    if judgment is not None and "infeasible" in judgment.reason:
        return "INFEASIBLE_MISMATCH"
    if judgment is not None and judgment.reason == "objective_mismatch":
        return "WRONG_OPT"
    return "CODEGEN_ERR"


def _utc_iso8601() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _write_failure_artifact(
    output_dir: Path,
    *,
    item: BenchmarkItem,
    track: str,
    repetition: int,
    checker_retry: str,
    text: str | None,
    translation: TranslationResult | None,
    attempt: BenchmarkAttempt | None,
    judgment: BenchmarkJudgment | None,
    error: str | None,
    failure_category: str,
    wall_sec: float,
    evaluated_at: str,
) -> Path:
    failures_dir = output_dir / "failures"
    failures_dir.mkdir(parents=True, exist_ok=True)
    safe_item_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.item_id)
    path = failures_dir / f"{item.dataset}-{safe_item_id}-{track}-r{repetition}-{checker_retry}.json"
    payload: dict[str, Any] = {
        "dataset": item.dataset,
        "item_id": item.item_id,
        "track": track,
        "repetition": repetition,
        "checker_retry": checker_retry,
        "source_text": item.question,
        "extraction_text": text,
        "ground_truth": item.ground_truth,
        "translation": asdict(translation) if translation is not None else None,
        "attempt": _attempt_payload(attempt) if attempt is not None else None,
        "judgment": judgment.to_dict() if judgment is not None else None,
        "failure_category": failure_category,
        "router_problem_type": _attempt_detail(attempt, "router_problem_type"),
        "router_reason": _attempt_detail(attempt, "router_reason"),
        "extractor_provider": _attempt_detail(attempt, "extractor_provider"),
        "extractor_model": _attempt_detail(attempt, "extractor_model"),
        "wall_sec": wall_sec,
        "evaluated_at": evaluated_at,
        "error": error,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _write_run_manifest(
    path: Path,
    config: BenchmarkRunConfig,
    dataset_names: tuple[str, ...],
    items: list[BenchmarkItem],
    started_at: str,
    completed_at: str,
) -> None:
    entries = {}
    for name in dataset_names:
        _, entry = _dataset_entry(name, config.datasets_dir)
        entries[name] = entry
    path.write_text(
        json.dumps(
            {
                "run_id": config.run_id,
                "dataset": config.dataset,
                "track": config.track,
                "repetitions": config.repetitions,
                "checker_retry": "on" if config.checker_retry else "off",
                "limit": config.limit,
                "timeout_sec": config.timeout_sec,
                "tolerance": config.tolerance,
                "translation_audit_fraction": config.audit_fraction,
                "started_at": started_at,
                "completed_at": completed_at,
                "datasets": entries,
                "selected_item_ids": {
                    dataset_name: [item.item_id for item in items if item.dataset == dataset_name]
                    for dataset_name in dataset_names
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_benchmark(config: BenchmarkRunConfig) -> Path:
    """Run the requested matrix, append one row per attempt, and return its CSV."""

    dataset_names = _selected_dataset_names(config.dataset)
    tracks = _selected_tracks(config.track)
    results_csv, audit_csv, run_manifest = _resolve_output_paths(config)
    results_csv.parent.mkdir(parents=True, exist_ok=True)
    all_items: list[BenchmarkItem] = []
    for dataset_name in dataset_names:
        items = load_benchmark_dataset(dataset_name, config.datasets_dir)
        all_items.extend(items[: config.limit] if config.limit is not None else items)
    started_at = _utc_iso8601()

    _validate_results_header(results_csv)
    existing_keys = _resume_keys(results_csv) if config.resume else set()
    audit_keys = _audit_item_keys(all_items, config.audit_fraction)
    results_needs_header = not results_csv.exists() or results_csv.stat().st_size == 0
    audit_needs_header = not audit_csv.exists() or audit_csv.stat().st_size == 0
    checker_retry_value = "on" if config.checker_retry else "off"
    client: LLMClient | None = config.client

    with results_csv.open("a", newline="", encoding="utf-8") as results_handle, audit_csv.open(
        "a", newline="", encoding="utf-8"
    ) as audit_handle:
        results_writer = csv.DictWriter(results_handle, fieldnames=_RESULT_FIELDS)
        audit_writer = csv.DictWriter(audit_handle, fieldnames=_AUDIT_FIELDS)
        if results_needs_header:
            results_writer.writeheader()
        if audit_needs_header:
            audit_writer.writeheader()

        for item in all_items:
            for track in tracks:
                for repetition in range(1, config.repetitions + 1):
                    key = (item.dataset, item.item_id, track, repetition, checker_retry_value)
                    if key in existing_keys:
                        continue

                    attempt_started = time.perf_counter()

                    translation: TranslationResult | None = None
                    extraction_text = item.question
                    attempt: BenchmarkAttempt | None = None
                    judgment: BenchmarkJudgment | None = None
                    checker_retried = False
                    error: str | None = None
                    status = "ERROR"

                    if track == "zh":
                        if client is None:
                            try:
                                client = DeepSeekClient(timeout_sec=config.timeout_sec)
                            except Exception as exc:
                                error = str(exc)
                                translation = TranslationResult(
                                    None, None, None, None, _number_tokens(item.question), (), False, 0, error
                                )
                        if client is not None:
                            translation = translate_to_chinese(item.question, client, sleep=config.sleep)
                        if translation.error is not None:
                            status = "translation_error"
                            error = translation.error
                        elif not translation.numbers_match:
                            status = "translation_number_mismatch"
                            error = "Arabic-number tokens changed during translation"
                        else:
                            extraction_text = str(translation.translated_text)

                        if (item.dataset, item.item_id) in audit_keys and translation is not None:
                            audit_writer.writerow(
                                {
                                    "dataset": item.dataset,
                                    "item_id": item.item_id,
                                    "repetition": repetition,
                                    "source_text": item.question,
                                    "translated_text": translation.translated_text or "",
                                    "source_number_tokens": _json_cell(translation.source_numbers),
                                    "translated_number_tokens": _json_cell(translation.translated_numbers),
                                    "numbers_match": translation.numbers_match,
                                    "translation_model": translation.model or "",
                                    "translation_usage": _json_cell(translation.usage),
                                    "human_audit_status": "pending",
                                    "human_audit_notes": "",
                                }
                            )

                    if error is None:
                        if config.attempt_runner is not None:
                            attempt = _normalise_attempt(config.attempt_runner(item, extraction_text, repetition, config))
                        else:
                            if client is None:
                                try:
                                    client = DeepSeekClient(timeout_sec=config.timeout_sec)
                                except Exception as exc:
                                    attempt = BenchmarkAttempt(status="API_ERROR", error=str(exc))
                            if client is not None:
                                attempt_dir = results_csv.parent / "work" / item.dataset / item.item_id / track / str(repetition)
                                attempt = _run_default_attempt(item, extraction_text, repetition, config, client, attempt_dir)
                        assert attempt is not None
                        attempt, checker_retried = _retry_checker(attempt, config)
                        status = attempt.status
                        judgment = judge_benchmark_result(
                            prediction={"status": attempt.status, "objective_value": attempt.objective_value},
                            ground_truth=item.ground_truth,
                            spec=attempt.spec,
                            checker_passed=attempt.checker_passed,
                            tolerance=config.tolerance,
                        )
                        if not judgment.passed_1e_6:
                            error = attempt.error or judgment.reason

                    failed = judgment is None or not judgment.passed_1e_6
                    wall_sec = time.perf_counter() - attempt_started
                    evaluated_at = _utc_iso8601()
                    failure_category = _failure_category(
                        status=status,
                        error=error,
                        attempt=attempt,
                        judgment=judgment,
                    )
                    artifact_path = None
                    if failed:
                        artifact_path = _write_failure_artifact(
                            results_csv.parent,
                            item=item,
                            track=track,
                            repetition=repetition,
                            checker_retry=checker_retry_value,
                            text=extraction_text,
                            translation=translation,
                            attempt=attempt,
                            judgment=judgment,
                            error=error,
                            failure_category=failure_category,
                            wall_sec=wall_sec,
                            evaluated_at=evaluated_at,
                        )
                        work_dir = _attempt_work_dir(attempt)
                        if work_dir is not None and work_dir.exists():
                            shutil.move(str(work_dir), str(artifact_path.with_suffix(".work")))
                    else:
                        work_dir = _attempt_work_dir(attempt)
                        if work_dir is not None:
                            shutil.rmtree(work_dir, ignore_errors=True)

                    results_writer.writerow(
                        {
                            "dataset": item.dataset,
                            "item_id": item.item_id,
                            "difficulty": str(item.raw.get("difficulty", "")),
                            "problem_type": _attempt_problem_type(attempt),
                            "track": track,
                            "repetition": repetition,
                            "checker_retry": checker_retry_value,
                            "status": status,
                            "checker_passed": bool(attempt and attempt.checker_passed),
                            "ground_truth": _json_cell(item.ground_truth),
                            "objective_value": "" if attempt is None or attempt.objective_value is None else attempt.objective_value,
                            "passed_1e_6": bool(judgment and judgment.passed_1e_6),
                            "passed_1e_4": bool(judgment and judgment.passed_1e_4),
                            "judgment_reason": judgment.reason if judgment is not None else "not_judged",
                            "translation_provider": translation.provider if translation and translation.provider else "",
                            "translation_model": translation.model if translation and translation.model else "",
                            "translation_usage": _json_cell(translation.usage if translation else None),
                            "translation_numbers_match": "" if translation is None else translation.numbers_match,
                            "api_attempts": translation.api_attempts if translation else 0,
                            "checker_retried": checker_retried,
                            "failure_category": failure_category,
                            "router_problem_type": _attempt_detail(attempt, "router_problem_type"),
                            "extractor_provider": _attempt_detail(attempt, "extractor_provider"),
                            "extractor_model": _attempt_detail(attempt, "extractor_model"),
                            "wall_sec": wall_sec,
                            "evaluated_at": evaluated_at,
                            "error": error or "",
                            "failure_artifact": str(artifact_path) if artifact_path else "",
                        }
                    )
    _write_run_manifest(
        run_manifest,
        config,
        dataset_names,
        all_items,
        started_at=started_at,
        completed_at=_utc_iso8601(),
    )
    return results_csv
