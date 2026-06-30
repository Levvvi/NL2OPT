from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = ROOT / "examples" / "specs"


def spec_path(name: str) -> Path:
    return SPECS_DIR / f"{name}.json"


def test_load_problem_spec_detects_production():
    from nl2opt.pipeline import load_problem_spec
    from nl2opt.schemas import ProductionProblemSpec

    spec = load_problem_spec(spec_path("production_basic"))

    assert isinstance(spec, ProductionProblemSpec)


def test_load_problem_spec_detects_assignment():
    from nl2opt.pipeline import load_problem_spec
    from nl2opt.schemas import AssignmentProblemSpec

    spec = load_problem_spec(spec_path("assignment_basic"))

    assert isinstance(spec, AssignmentProblemSpec)


def test_load_problem_spec_detects_jobshop():
    from nl2opt.pipeline import load_problem_spec
    from nl2opt.schemas import JobshopProblemSpec

    spec = load_problem_spec(spec_path("jobshop_basic"))

    assert isinstance(spec, JobshopProblemSpec)


def test_load_problem_spec_detects_vrp():
    from nl2opt.pipeline import load_problem_spec
    from nl2opt.schemas import VrpProblemSpec

    spec = load_problem_spec(spec_path("vrp_basic"))

    assert isinstance(spec, VrpProblemSpec)


def test_render_code_for_spec_all_four_types():
    from nl2opt.pipeline import load_problem_spec, render_code_for_spec

    rendered = {
        name: render_code_for_spec(load_problem_spec(spec_path(name)))
        for name in [
            "production_basic",
            "assignment_basic",
            "jobshop_basic",
            "vrp_basic",
        ]
    }

    assert "linear_solver" in rendered["production_basic"]
    assert "BoolVar" in rendered["assignment_basic"]
    assert "cp_model" in rendered["jobshop_basic"]
    assert "RoutingModel" in rendered["vrp_basic"]


def test_run_problem_file_production_basic(tmp_path):
    from nl2opt.pipeline import run_problem_file

    result = run_problem_file(spec_path("production_basic"), tmp_path / "production")

    assert result.checker_passed is True
    assert result.objective_value == 2200
    assert result.solver_status == "OPTIMAL"


def test_run_problem_file_assignment_basic(tmp_path):
    from nl2opt.pipeline import run_problem_file

    result = run_problem_file(spec_path("assignment_basic"), tmp_path / "assignment")

    assert result.checker_passed is True
    assert result.objective_value == 21
    assert result.solver_status == "OPTIMAL"


def test_run_problem_file_jobshop_basic(tmp_path):
    from nl2opt.pipeline import run_problem_file

    result = run_problem_file(spec_path("jobshop_basic"), tmp_path / "jobshop")

    assert result.checker_passed is True
    assert result.objective_value == 7
    assert result.solver_status == "OPTIMAL"


def test_run_problem_file_vrp_basic(tmp_path):
    from nl2opt.pipeline import run_problem_file

    result = run_problem_file(spec_path("vrp_basic"), tmp_path / "vrp", timeout_sec=10)

    assert result.checker_passed is True
    assert result.objective_value == 44
    assert result.solver_status in {"FEASIBLE", "OPTIMAL"}


def test_pipeline_writes_report_json(tmp_path):
    from nl2opt.pipeline import run_problem_file

    result = run_problem_file(spec_path("production_basic"), tmp_path / "report")
    report_path = Path(result.report_path)

    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report_path.exists()
    assert report["problem_id"] == "production_basic"
    assert report["problem_type"] == "production"
    assert report["checker_passed"] is True
    assert report["solution_path"] == result.solution_path
    assert "generated_model.py" not in report


def test_pipeline_rejects_unsupported_problem_type(tmp_path):
    from nl2opt.pipeline import run_problem_file

    unsupported_path = tmp_path / "unsupported.json"
    unsupported_path.write_text(
        json.dumps(
            {
                "problem_id": "bad_case",
                "problem_type": "unsupported_kind",
            }
        ),
        encoding="utf-8",
    )

    result = run_problem_file(unsupported_path, tmp_path / "unsupported_output")

    assert result.checker_passed is False
    assert result.error is not None
    assert "unsupported problem_type" in result.error
