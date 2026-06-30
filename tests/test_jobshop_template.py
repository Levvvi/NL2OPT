from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOBSHOP_SPEC_PATH = ROOT / "examples" / "specs" / "jobshop_basic.json"
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"
ASSIGNMENT_SPEC_PATH = ROOT / "examples" / "specs" / "assignment_basic.json"


def load_jobshop_spec():
    from nl2opt.schemas import JobshopProblemSpec

    return JobshopProblemSpec.model_validate_json(
        JOBSHOP_SPEC_PATH.read_text(encoding="utf-8")
    )


def test_render_jobshop_code_contains_cp_sat():
    from nl2opt.solvers.render import render_jobshop_code

    code = render_jobshop_code(load_jobshop_spec())

    assert "from ortools.sat.python import cp_model" in code
    assert "NewIntervalVar" in code
    assert "solution.json" in code


def test_render_jobshop_code_contains_no_overlap():
    from nl2opt.solvers.render import render_jobshop_code

    code = render_jobshop_code(load_jobshop_spec())

    assert "AddNoOverlap" in code
    assert "AddMaxEquality" in code


def test_render_jobshop_code_has_no_unresolved_jinja_placeholders():
    from nl2opt.solvers.render import render_jobshop_code

    code = render_jobshop_code(load_jobshop_spec())

    assert "{{" not in code
    assert "}}" not in code
    assert "{%" not in code
    assert "%}" not in code


def test_render_jobshop_code_keeps_existing_renderers_working():
    from nl2opt.schemas import AssignmentProblemSpec, ProductionProblemSpec
    from nl2opt.solvers.render import render_assignment_code, render_production_code

    production_spec = ProductionProblemSpec.model_validate_json(
        PRODUCTION_SPEC_PATH.read_text(encoding="utf-8")
    )
    assignment_spec = AssignmentProblemSpec.model_validate_json(
        ASSIGNMENT_SPEC_PATH.read_text(encoding="utf-8")
    )

    assert "quantities" in render_production_code(production_spec)
    assert "assignments" in render_assignment_code(assignment_spec)
