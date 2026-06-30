from __future__ import annotations

import json


def test_runner_executes_simple_code_and_writes_solution(tmp_path):
    from nl2opt.runtime.runner import load_solver_result, run_python_code

    code = """
import json

with open("solution.json", "w", encoding="utf-8") as output_file:
    json.dump({
        "status": "OPTIMAL",
        "objective_value": 1,
        "solution": {"quantities": {"A": 1}},
        "runtime_sec": 0.01,
        "solver": "unit-test",
        "violations": [],
    }, output_file)
"""

    run_result = run_python_code(code, tmp_path)

    assert run_result.returncode == 0
    assert run_result.timed_out is False
    assert run_result.code_path.exists()
    assert run_result.solution_path.exists()
    solver_result = load_solver_result(run_result.solution_path)
    assert solver_result.objective_value == 1


def test_runner_timeout(tmp_path):
    from nl2opt.runtime.runner import run_python_code

    code = """
import time

time.sleep(2)
"""

    run_result = run_python_code(code, tmp_path, timeout_sec=1)

    assert run_result.timed_out is True
    assert run_result.returncode is None


def test_runner_executes_with_relative_workdir(tmp_path, monkeypatch):
    from pathlib import Path

    from nl2opt.runtime.runner import run_python_code

    monkeypatch.chdir(tmp_path)
    code = """
import json

with open("solution.json", "w", encoding="utf-8") as output_file:
    json.dump({
        "status": "OPTIMAL",
        "objective_value": 1,
        "solution": {},
        "runtime_sec": 0.01,
        "solver": "unit-test",
        "violations": [],
    }, output_file)
"""

    run_result = run_python_code(code, Path("relative_run"))

    assert run_result.returncode == 0, run_result.stderr
    assert run_result.solution_path.exists()
