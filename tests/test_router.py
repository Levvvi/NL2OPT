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


def test_route_bilingual_generic_linear_programs():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    english = route_text(
        "Maximize 3x + 2y subject to linear constraints; x and y are decision variables."
    )
    chinese = route_text(
        "\u8fd9\u662f\u4e00\u4e2a\u7ebf\u6027\u89c4\u5212\u95ee\u9898\uff0c\u51b3\u7b56\u53d8\u91cf x \u548c y \u9700\u6ee1\u8db3\u7ebf\u6027\u7ea6\u675f\u3002"
    )

    assert english.problem_type is ProblemType.GENERIC_LP_MILP
    assert chinese.problem_type is ProblemType.GENERIC_LP_MILP


def test_route_explicit_linear_program_keyword_to_generic_lp_milp():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("This is a linear program.")

    assert result.problem_type is ProblemType.GENERIC_LP_MILP


def test_route_ordinary_english_and_chinese_optimization_wording_to_generic_lp_milp():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    english = route_text(
        "Minimize total transport time when there can be at most 12 boat trips and at least 60% use canoes."
    )
    chinese = route_text("最小化总时间，x 至少为 10，且 x 不超过 100。")

    assert english.problem_type is ProblemType.GENERIC_LP_MILP
    assert chinese.problem_type is ProblemType.GENERIC_LP_MILP


def test_route_plain_constraint_phrase_without_an_optimization_signal_is_unsupported():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("Please write a poem with at most twelve lines.")

    assert result.problem_type is ProblemType.UNSUPPORTED


def test_route_bare_cost_noun_without_an_optimization_verb_is_unsupported():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    result = route_text("The cost of this book is five dollars.")

    assert result.problem_type is ProblemType.UNSUPPORTED


def test_route_rejects_clear_nonlinear_stochastic_and_dynamic_requests():
    from nl2opt.agents.router import route_text
    from nl2opt.schemas import ProblemType

    for text in (
        "Maximize x squared subject to nonlinear constraints.",
        "Optimize a stochastic linear program with random demand.",
        "\u8fd9\u662f\u4e00\u4e2a\u52a8\u6001\u4f18\u5316\u95ee\u9898\uff0c\u9700\u8981\u8003\u8651\u968f\u673a\u9700\u6c42\u3002",
    ):
        assert route_text(text).problem_type is ProblemType.UNSUPPORTED
