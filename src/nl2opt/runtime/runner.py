from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from nl2opt.schemas import SolverResult


@dataclass(frozen=True)
class RunResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    code_path: Path
    solution_path: Path
    runtime_sec: float


def _output_to_text(output: bytes | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def run_python_code(code: str, workdir: Path, timeout_sec: int = 5) -> RunResult:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    workdir = workdir.resolve()
    code_path = workdir / "generated_model.py"
    solution_path = workdir / "solution.json"
    code_path.write_text(code, encoding="utf-8")

    start = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, str(code_path)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return RunResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
            code_path=code_path,
            solution_path=solution_path,
            runtime_sec=time.perf_counter() - start,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            returncode=None,
            stdout=_output_to_text(exc.stdout),
            stderr=_output_to_text(exc.stderr),
            timed_out=True,
            code_path=code_path,
            solution_path=solution_path,
            runtime_sec=time.perf_counter() - start,
        )


def load_solver_result(solution_path: Path) -> SolverResult:
    return SolverResult.model_validate_json(Path(solution_path).read_text(encoding="utf-8"))
