from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from nl2opt.checkers.base import CheckerReport
from nl2opt.checkers.assignment_checker import check_assignment_solution
from nl2opt.checkers.generic_lp_checker import check_generic_solution
from nl2opt.checkers.jobshop_checker import check_jobshop_solution
from nl2opt.checkers.production_checker import check_production_solution
from nl2opt.checkers.vrp_checker import check_vrp_solution
from nl2opt.runtime.runner import load_solver_result, run_python_code
from nl2opt.schemas import (
    AssignmentProblemSpec,
    GenericLpSpec,
    JobshopProblemSpec,
    ProblemType,
    ProductionProblemSpec,
    SolverResult,
    VrpProblemSpec,
)
from nl2opt.solvers.render import (
    render_assignment_code,
    render_generic_lp_code,
    render_jobshop_code,
    render_production_code,
    render_vrp_code,
)


MAX_REPORT_TEXT = 4000


@dataclass
class PipelineResult:
    problem_id: str
    problem_type: str
    output_dir: str
    code_path: str | None
    solution_path: str | None
    report_path: str | None
    returncode: int | None
    timed_out: bool
    solver_status: str | None
    objective_value: float | None
    checker_passed: bool
    violations: list[str]
    runtime_sec: float | None
    stdout: str
    stderr: str
    error: str | None

    def to_report_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["stdout"] = _truncate(data["stdout"])
        data["stderr"] = _truncate(data["stderr"])
        return data


def _truncate(value: str) -> str:
    if len(value) <= MAX_REPORT_TEXT:
        return value
    return value[:MAX_REPORT_TEXT] + "...<truncated>"


def _problem_type_value(spec: Any) -> str:
    problem_type = getattr(spec, "problem_type", "")
    if isinstance(problem_type, ProblemType):
        return problem_type.value
    return str(problem_type)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("ProblemSpec JSON must be an object")
    return data


def _peek_field(path: Path, field_name: str, fallback: str) -> str:
    try:
        data = _read_json(path)
    except Exception:
        return fallback
    value = data.get(field_name)
    return str(value) if value is not None else fallback


def load_problem_spec(path: Path) -> Any:
    data = _read_json(Path(path))
    problem_type = data.get("problem_type")
    if problem_type is None:
        raise ValueError("problem_type is required")

    schema_by_type: dict[str, type[Any]] = {
        ProblemType.PRODUCTION.value: ProductionProblemSpec,
        ProblemType.ASSIGNMENT.value: AssignmentProblemSpec,
        ProblemType.JOBSHOP.value: JobshopProblemSpec,
        ProblemType.VRP.value: VrpProblemSpec,
        ProblemType.GENERIC_LP_MILP.value: GenericLpSpec,
    }
    schema_class = schema_by_type.get(str(problem_type))
    if schema_class is None:
        raise ValueError(f"unsupported problem_type: {problem_type}")

    return schema_class.model_validate(data)


def render_code_for_spec(spec: Any) -> str:
    problem_type = _problem_type_value(spec)
    if problem_type == ProblemType.PRODUCTION.value:
        return render_production_code(spec)
    if problem_type == ProblemType.ASSIGNMENT.value:
        return render_assignment_code(spec)
    if problem_type == ProblemType.JOBSHOP.value:
        return render_jobshop_code(spec)
    if problem_type == ProblemType.VRP.value:
        return render_vrp_code(spec)
    if problem_type == ProblemType.GENERIC_LP_MILP.value:
        return render_generic_lp_code(spec)
    raise ValueError(f"unsupported problem_type: {problem_type}")


def check_result_for_spec(
    spec: Any,
    result: SolverResult,
    *,
    timeout_sec: float | None = None,
) -> CheckerReport:
    problem_type = _problem_type_value(spec)
    if problem_type == ProblemType.PRODUCTION.value:
        return check_production_solution(spec, result)
    if problem_type == ProblemType.ASSIGNMENT.value:
        return check_assignment_solution(spec, result)
    if problem_type == ProblemType.JOBSHOP.value:
        return check_jobshop_solution(spec, result)
    if problem_type == ProblemType.VRP.value:
        return check_vrp_solution(spec, result)
    if problem_type == ProblemType.GENERIC_LP_MILP.value:
        return check_generic_solution(spec, result, timeout_sec=timeout_sec)
    raise ValueError(f"unsupported problem_type: {problem_type}")


def _write_pipeline_report(result: PipelineResult, output_dir: Path) -> PipelineResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "pipeline_report.json"
    result.report_path = str(report_path)
    report_path.write_text(
        json.dumps(result.to_report_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def _new_result(
    *,
    problem_id: str,
    problem_type: str,
    output_dir: Path,
    error: str | None = None,
) -> PipelineResult:
    return PipelineResult(
        problem_id=problem_id,
        problem_type=problem_type,
        output_dir=str(output_dir),
        code_path=None,
        solution_path=None,
        report_path=None,
        returncode=None,
        timed_out=False,
        solver_status=None,
        objective_value=None,
        checker_passed=False,
        violations=[] if error is None else [error],
        runtime_sec=None,
        stdout="",
        stderr="",
        error=error,
    )


def run_problem_spec(
    spec: Any,
    output_dir: Path,
    timeout_sec: int = 10,
) -> PipelineResult:
    output_dir = Path(output_dir)
    result = _new_result(
        problem_id=str(getattr(spec, "problem_id", "unknown")),
        problem_type=_problem_type_value(spec),
        output_dir=output_dir,
    )

    try:
        code = render_code_for_spec(spec)
    except Exception as exc:
        result.error = f"render failed: {exc}"
        result.violations = [result.error]
        return _write_pipeline_report(result, output_dir)

    solver_started = time.monotonic()
    run_result = run_python_code(code, output_dir, timeout_sec=timeout_sec)
    checker_timeout_sec = timeout_sec - (time.monotonic() - solver_started)
    result.code_path = str(run_result.code_path)
    result.solution_path = str(run_result.solution_path)
    result.returncode = run_result.returncode
    result.timed_out = run_result.timed_out
    result.runtime_sec = run_result.runtime_sec
    result.stdout = run_result.stdout
    result.stderr = run_result.stderr

    if run_result.timed_out:
        result.error = f"runner timed out after {timeout_sec} seconds"
        result.violations = [result.error]
        return _write_pipeline_report(result, output_dir)

    if not run_result.solution_path.exists():
        result.error = "solution.json was not generated"
        if run_result.returncode not in (None, 0):
            result.error += f"; returncode={run_result.returncode}"
        result.violations = [result.error]
        return _write_pipeline_report(result, output_dir)

    try:
        solver_result = load_solver_result(run_result.solution_path)
    except (ValidationError, ValueError, OSError) as exc:
        result.error = f"failed to parse SolverResult: {exc}"
        result.violations = [result.error]
        return _write_pipeline_report(result, output_dir)

    result.solver_status = solver_result.status.value
    result.objective_value = solver_result.objective_value

    try:
        checker_report = check_result_for_spec(spec, solver_result, timeout_sec=checker_timeout_sec)
    except Exception as exc:
        result.error = f"checker failed to run: {exc}"
        result.violations = [result.error]
        return _write_pipeline_report(result, output_dir)

    result.checker_passed = checker_report.passed
    result.violations = checker_report.violations
    if not checker_report.passed:
        result.error = "checker failed"

    return _write_pipeline_report(result, output_dir)


def run_problem_file(
    spec_path: Path,
    output_dir: Path | None = None,
    timeout_sec: int = 10,
) -> PipelineResult:
    spec_path = Path(spec_path)
    output_dir = Path(output_dir) if output_dir is not None else Path("outputs") / "pipeline" / spec_path.stem

    try:
        spec = load_problem_spec(spec_path)
    except Exception as exc:
        problem_id = _peek_field(spec_path, "problem_id", spec_path.stem)
        problem_type = _peek_field(spec_path, "problem_type", "unknown")
        result = _new_result(
            problem_id=problem_id,
            problem_type=problem_type,
            output_dir=output_dir,
            error=str(exc),
        )
        return _write_pipeline_report(result, output_dir)

    return run_problem_spec(spec, output_dir, timeout_sec=timeout_sec)


def _print_result(result: PipelineResult) -> None:
    print(f"problem_id: {result.problem_id}")
    print(f"problem_type: {result.problem_type}")
    print(f"solver_status: {result.solver_status}")
    print(f"objective_value: {result.objective_value}")
    print(f"checker_passed: {result.checker_passed}")
    print(f"violations: {result.violations}")
    print(f"report_path: {result.report_path}")
    if result.error:
        print(f"error: {result.error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an NL2OPT ProblemSpec through the local pipeline.")
    parser.add_argument("spec_path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--timeout-sec", type=int, default=10)
    args = parser.parse_args(argv)

    result = run_problem_file(
        args.spec_path,
        output_dir=args.output_dir,
        timeout_sec=args.timeout_sec,
    )
    _print_result(result)
    return 0 if result.checker_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
