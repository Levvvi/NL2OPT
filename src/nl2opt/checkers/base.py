from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckerReport:
    passed: bool
    violations: list[str] = field(default_factory=list)
    computed_objective: float | None = None
    resource_usage: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
