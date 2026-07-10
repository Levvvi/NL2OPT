from __future__ import annotations

import json
from importlib.resources import files

from jinja2 import Environment, StrictUndefined

from nl2opt.schemas import (
    AssignmentProblemSpec,
    GenericLpSpec,
    JobshopProblemSpec,
    ProductionProblemSpec,
    VrpProblemSpec,
)


def _render_template(template_name: str, spec_dict: dict) -> str:
    template_text = (
        files("nl2opt.solvers.templates")
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )
    environment = Environment(
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.from_string(template_text)
    return template.render(
        spec=spec_dict,
        spec_json=json.dumps(spec_dict, ensure_ascii=False, indent=2),
    )


def render_production_code(spec: ProductionProblemSpec) -> str:
    return _render_template("production.py.j2", spec.model_dump(mode="json"))


def render_assignment_code(spec: AssignmentProblemSpec) -> str:
    return _render_template("assignment.py.j2", spec.model_dump(mode="json"))


def render_jobshop_code(spec: JobshopProblemSpec) -> str:
    return _render_template("jobshop.py.j2", spec.model_dump(mode="json"))


def render_vrp_code(spec: VrpProblemSpec) -> str:
    return _render_template("vrp.py.j2", spec.model_dump(mode="json"))


def render_generic_lp_code(spec: GenericLpSpec) -> str:
    return _render_template("generic_lp.py.j2", spec.model_dump(mode="json"))
