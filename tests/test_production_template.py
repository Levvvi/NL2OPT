from __future__ import annotations

import json
from pathlib import Path

from nl2opt.schemas import ProductionProblemSpec


SPEC_PATH = Path(__file__).resolve().parents[1] / "examples" / "specs" / "production_basic.json"


def load_spec() -> ProductionProblemSpec:
    return ProductionProblemSpec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))


def test_render_production_code_contains_ortools():
    from nl2opt.solvers.render import render_production_code

    code = render_production_code(load_spec())

    assert "from ortools.linear_solver import pywraplp" in code
    assert "CreateSolver" in code
    assert "solution.json" in code


def test_render_production_code_has_no_unresolved_jinja_placeholders():
    from nl2opt.solvers.render import render_production_code

    code = render_production_code(load_spec())

    assert "{{" not in code
    assert "}}" not in code
    assert "{%" not in code
    assert "%}" not in code
