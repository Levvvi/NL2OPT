from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VRP_SPEC_PATH = ROOT / "examples" / "specs" / "vrp_basic.json"
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"
ASSIGNMENT_SPEC_PATH = ROOT / "examples" / "specs" / "assignment_basic.json"
JOBSHOP_SPEC_PATH = ROOT / "examples" / "specs" / "jobshop_basic.json"


def load_vrp_spec():
    from nl2opt.schemas import VrpProblemSpec

    return VrpProblemSpec.model_validate_json(VRP_SPEC_PATH.read_text(encoding="utf-8"))


def test_render_vrp_code_contains_routing_model():
    from nl2opt.solvers.render import render_vrp_code

    code = render_vrp_code(load_vrp_spec())

    assert "from ortools.constraint_solver import pywrapcp" in code
    assert "RoutingIndexManager" in code
    assert "RoutingModel" in code


def test_render_vrp_code_contains_capacity_dimension():
    from nl2opt.solvers.render import render_vrp_code

    code = render_vrp_code(load_vrp_spec())

    assert "AddDimensionWithVehicleCapacity" in code
    assert "RegisterUnaryTransitCallback" in code


def test_render_vrp_code_has_no_unresolved_jinja_placeholders():
    from nl2opt.solvers.render import render_vrp_code

    code = render_vrp_code(load_vrp_spec())

    assert "{{" not in code
    assert "}}" not in code
    assert "{%" not in code
    assert "%}" not in code


def test_render_vrp_code_keeps_existing_renderers_working():
    from nl2opt.schemas import AssignmentProblemSpec, JobshopProblemSpec, ProductionProblemSpec
    from nl2opt.solvers.render import (
        render_assignment_code,
        render_jobshop_code,
        render_production_code,
    )

    production_spec = ProductionProblemSpec.model_validate_json(
        PRODUCTION_SPEC_PATH.read_text(encoding="utf-8")
    )
    assignment_spec = AssignmentProblemSpec.model_validate_json(
        ASSIGNMENT_SPEC_PATH.read_text(encoding="utf-8")
    )
    jobshop_spec = JobshopProblemSpec.model_validate_json(
        JOBSHOP_SPEC_PATH.read_text(encoding="utf-8")
    )

    assert "quantities" in render_production_code(production_spec)
    assert "assignments" in render_assignment_code(assignment_spec)
    assert "AddNoOverlap" in render_jobshop_code(jobshop_spec)
