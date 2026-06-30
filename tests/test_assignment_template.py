from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT_SPEC_PATH = ROOT / "examples" / "specs" / "assignment_basic.json"
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"


def load_assignment_spec():
    from nl2opt.schemas import AssignmentProblemSpec

    return AssignmentProblemSpec.model_validate_json(
        ASSIGNMENT_SPEC_PATH.read_text(encoding="utf-8")
    )


def test_render_assignment_code_contains_ortools():
    from nl2opt.solvers.render import render_assignment_code

    code = render_assignment_code(load_assignment_spec())

    assert "from ortools.linear_solver import pywraplp" in code
    assert "BoolVar" in code
    assert "solution.json" in code


def test_render_assignment_code_has_no_unresolved_jinja_placeholders():
    from nl2opt.solvers.render import render_assignment_code

    code = render_assignment_code(load_assignment_spec())

    assert "{{" not in code
    assert "}}" not in code
    assert "{%" not in code
    assert "%}" not in code


def test_render_assignment_code_keeps_production_renderer_working():
    from nl2opt.schemas import ProductionProblemSpec
    from nl2opt.solvers.render import render_production_code

    spec = ProductionProblemSpec.model_validate_json(
        PRODUCTION_SPEC_PATH.read_text(encoding="utf-8")
    )
    code = render_production_code(spec)

    assert "from ortools.linear_solver import pywraplp" in code
    assert "quantities" in code
