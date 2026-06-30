from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_mock_case(text: str, problem_type: str, spec_name: str, tmp_path: Path):
    from nl2opt.agents.extractor import extract_problem_spec
    from nl2opt.agents.llm_client import MockLLMClient
    from nl2opt.pipeline import run_problem_spec

    spec_path = ROOT / "examples" / "specs" / spec_name
    result = extract_problem_spec(
        text,
        problem_type=problem_type,
        client=MockLLMClient(json.loads(spec_path.read_text(encoding="utf-8"))),
    )
    assert result.success is True, result.error
    return run_problem_spec(result.spec, tmp_path / spec_path.stem)


def test_mock_nl_pipeline_production_tiny(tmp_path):
    result = run_mock_case(
        "小工厂生产 X 和 Y 两种产品，利润和材料工时不同，想最大化 profit。",
        "production",
        "production_tiny.json",
        tmp_path,
    )

    assert result.checker_passed is True
    assert result.objective_value == 23


def test_mock_nl_pipeline_assignment_tiny(tmp_path):
    result = run_mock_case(
        "把任务 A 和 B 分配给员工 E1、E2，每人最多一个任务，总成本最低。",
        "assignment",
        "assignment_tiny.json",
        tmp_path,
    )

    assert result.checker_passed is True
    assert result.objective_value == 5


def test_mock_nl_pipeline_jobshop_tiny(tmp_path):
    result = run_mock_case(
        "两个工件按工序在 M1、M2 机器上加工，要求排产后 makespan 最短。",
        "jobshop",
        "jobshop_tiny.json",
        tmp_path,
    )

    assert result.checker_passed is True
    assert result.objective_value == 3


def test_mock_nl_pipeline_vrp_tiny(tmp_path):
    result = run_mock_case(
        "一辆车从 depot 出发配送 C1、C2、C3，车辆容量够用，要求总路程最短。",
        "vrp",
        "vrp_tiny.json",
        tmp_path,
    )

    assert result.checker_passed is True
    assert result.objective_value == 12


def test_run_mock_nl_basic_script(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "run_mock_nl_basic.py"),
            "--output-dir",
            str(tmp_path / "mock_eval"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "extractor_production_01" in completed.stdout
    assert "extractor_vrp_02" in completed.stdout
    assert "PASS" in completed.stdout
