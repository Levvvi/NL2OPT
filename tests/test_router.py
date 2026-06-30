from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_route_production_text():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大？")

    assert result.problem_type is ProblemType.PRODUCTION
    assert result.confidence > 0
    assert "生产" in result.matched_keywords


def test_route_assignment_text():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("把多个维修任务指派给不同技师，每个任务只能分配给一人，希望总成本最低。")

    assert result.problem_type is ProblemType.ASSIGNMENT
    assert "任务" in result.matched_keywords


def test_route_jobshop_text():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("几个工件要按工序先后顺序在不同机器上加工，目标是最小化最大完工时间。")

    assert result.problem_type is ProblemType.JOBSHOP
    assert "工序" in result.matched_keywords


def test_route_vrp_text():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("两辆车从仓库出发给多个客户配送，车辆容量有限，希望总路程最短。")

    assert result.problem_type is ProblemType.VRP
    assert "车辆" in result.matched_keywords


def test_route_empty_text_returns_unsupported():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("   \n\t")

    assert result.problem_type is ProblemType.UNSUPPORTED
    assert result.confidence == 0.0
    assert result.matched_keywords == []


def test_route_unrelated_text_returns_unsupported():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("帮我写一首关于春天的诗，并解释一下梯度下降。")

    assert result.problem_type is ProblemType.UNSUPPORTED
    assert result.confidence == 0.0


def test_router_result_has_reason_and_keywords():
    from nl2opt.agents.router import route_text

    result = route_text("员工需要分配到不同客户请求，每个任务有不同处理成本。")

    assert result.reason
    assert result.matched_keywords
    assert 0.0 <= result.confidence <= 1.0


def test_router_cli_runs():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.router",
            "某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大？",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["problem_type"] == "production"
    assert payload["confidence"] > 0
