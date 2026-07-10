from __future__ import annotations

import argparse
import json

from pydantic import Field

from nl2opt.schemas import ProblemType
from nl2opt.schemas.base import StrictBaseModel


class RouterResult(StrictBaseModel):
    problem_type: ProblemType
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str]
    reason: str


KEYWORDS: dict[ProblemType, list[str]] = {
    ProblemType.PRODUCTION: [
        "工厂",
        "生产",
        "产品",
        "利润",
        "原料",
        "工时",
        "资源",
        "产量",
        "最大利润",
        "成本最小",
        "生产计划",
        "材料",
        "库存限制",
        "配方",
        "订单",
        "班次",
    ],
    ProblemType.ASSIGNMENT: [
        "员工",
        "任务",
        "分配",
        "指派",
        "安排人员",
        "每个任务",
        "成本矩阵",
        "能力",
        "容量",
        "派给",
        "负责人",
        "工作分派",
        "技师",
        "客服",
        "工单",
        "拣货员",
    ],
    ProblemType.JOBSHOP: [
        "工件",
        "工序",
        "机器",
        "加工",
        "排产",
        "车间",
        "完工时间",
        "最大完工时间",
        "makespan",
        "先后顺序",
        "不可重叠",
        "CNC",
        "订单",
        "包装",
    ],
    ProblemType.VRP: [
        "车辆",
        "配送",
        "客户",
        "仓库",
        "路线",
        "路径",
        "司机",
        "容量",
        "需求量",
        "总路程",
        "送货",
        "配送中心",
        "车辆路径",
        "距离矩阵",
        "不能超载",
    ],
}


DIRECT_GENERIC_LP_MILP_KEYWORDS = [
    "linear programming",
    "linear program",
    "integer programming",
    "mixed integer",
    "milp",
    "线性规划",
    "整数规划",
    "混合整数",
    "混合整数规划",
]

KEYWORDS[ProblemType.GENERIC_LP_MILP] = [
    *DIRECT_GENERIC_LP_MILP_KEYWORDS,
    "decision variable",
    "decision variables",
    "linear constraint",
    "linear constraints",
    "subject to",
    "决策变量",
    "线性约束",
]

REJECTION_KEYWORDS = [
    "nonlinear",
    "quadratic",
    "stochastic",
    "random demand",
    "dynamic optimization",
    "非线性",
    "二次",
    "随机",
    "不确定",
    "动态优化",
]

GENERIC_OBJECTIVE_VERB_SIGNALS = [
    "minimize",
    "maximize",
    "最小化",
    "最大化",
]

GENERIC_OBJECTIVE_NOUN_SIGNALS = [
    "objective",
    "profit",
    "cost",
    "目标",
    "利润",
    "成本",
]

GENERIC_MODELING_SIGNALS = [
    "linear programming",
    "integer programming",
    "mixed integer",
    "milp",
    "decision variable",
    "linear constraint",
    "线性规划",
    "整数规划",
    "混合整数",
    "决策变量",
    "线性约束",
]

GENERIC_CONSTRAINT_SIGNALS = [
    "at most",
    "at least",
    "subject to",
    "constraint",
    "至多",
    "至少",
    "约束",
    "满足以下约束",
    "不超过",
    "不少于",
]


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def _score(text: str, problem_type: ProblemType, matches: list[str]) -> float:
    score = float(len(matches))

    if problem_type is ProblemType.VRP:
        route_terms = [
            "车辆",
            "配送",
            "路线",
            "仓库",
            "客户",
            "配送中心",
            "车辆路径",
            "送货",
            "司机",
            "路径",
        ]
        constraint_terms = ["容量", "需求量", "总路程", "距离", "不能超载"]
        if any(term in text for term in route_terms) and any(term in text for term in constraint_terms):
            score += 2.0
    elif problem_type is ProblemType.JOBSHOP:
        priority_terms = ["工序", "机器", "加工", "完工时间", "先后顺序", "不可重叠", "排产"]
        if sum(1 for term in priority_terms if term in text) >= 2:
            score += 1.5
    elif problem_type is ProblemType.ASSIGNMENT:
        priority_terms = ["员工", "任务", "分配", "指派", "派给", "负责人", "工单"]
        if sum(1 for term in priority_terms if term in text) >= 2:
            score += 1.0
    elif problem_type is ProblemType.PRODUCTION:
        priority_terms = ["产品", "生产", "利润", "原料", "工时", "产量", "材料"]
        if sum(1 for term in priority_terms if term in text) >= 2:
            score += 1.0

    elif problem_type is ProblemType.GENERIC_LP_MILP:
        priority_terms = [
            "linear",
            "integer",
            "milp",
            "decision variable",
            "subject to",
            "线性规划",
            "整数规划",
            "混合整数",
            "决策变量",
            "线性约束",
        ]
        if sum(1 for term in priority_terms if term in text.lower()) >= 2:
            score += 1.0

    return score


def _confidence(top_score: float, second_score: float, matched_count: int) -> float:
    if matched_count == 0:
        return 0.0
    margin = max(0.0, top_score - second_score)
    confidence = 0.45 + 0.1 * matched_count + 0.05 * margin
    if margin < 1.0:
        confidence -= 0.15
    return round(max(0.1, min(0.95, confidence)), 2)


def route_text(text: str) -> RouterResult:
    normalized = text.strip()
    if not normalized:
        return RouterResult(
            problem_type=ProblemType.UNSUPPORTED,
            confidence=0.0,
            matched_keywords=[],
            reason="输入为空，无法判断问题类型",
        )

    rejected_keywords = _matched_keywords(normalized, REJECTION_KEYWORDS)
    if rejected_keywords:
        return RouterResult(
            problem_type=ProblemType.UNSUPPORTED,
            confidence=0.95,
            matched_keywords=rejected_keywords,
            reason="clear nonlinear, stochastic, or dynamic optimization wording is unsupported",
        )

    direct_generic_matches = _matched_keywords(normalized, DIRECT_GENERIC_LP_MILP_KEYWORDS)
    if direct_generic_matches:
        return RouterResult(
            problem_type=ProblemType.GENERIC_LP_MILP,
            confidence=_confidence(float(len(direct_generic_matches)), 0.0, len(direct_generic_matches)),
            matched_keywords=direct_generic_matches,
            reason="matched explicit generic LP/MILP wording",
        )

    matches_by_type = {
        problem_type: _matched_keywords(normalized, keywords)
        for problem_type, keywords in KEYWORDS.items()
    }
    specialized_types = (
        ProblemType.PRODUCTION,
        ProblemType.ASSIGNMENT,
        ProblemType.JOBSHOP,
        ProblemType.VRP,
    )
    if not any(matches_by_type[problem_type] for problem_type in specialized_types):
        objective_verb_matches = _matched_keywords(normalized, GENERIC_OBJECTIVE_VERB_SIGNALS)
        objective_noun_matches = _matched_keywords(normalized, GENERIC_OBJECTIVE_NOUN_SIGNALS)
        modeling_matches = _matched_keywords(normalized, GENERIC_MODELING_SIGNALS)
        constraint_matches = _matched_keywords(normalized, GENERIC_CONSTRAINT_SIGNALS)
        generic_matches = list(
            dict.fromkeys(
                [
                    *matches_by_type[ProblemType.GENERIC_LP_MILP],
                    *objective_verb_matches,
                    *objective_noun_matches,
                    *modeling_matches,
                    *constraint_matches,
                ]
            )
        )
        noun_with_modeling_structure = bool(
            objective_noun_matches and modeling_matches and constraint_matches
        )
        if objective_verb_matches or len(modeling_matches) >= 2 or noun_with_modeling_structure:
            return RouterResult(
                problem_type=ProblemType.GENERIC_LP_MILP,
                confidence=_confidence(float(len(generic_matches)), 0.0, len(generic_matches)),
                matched_keywords=generic_matches,
                reason="matched generic optimization objective or modeling wording",
            )
        if generic_matches:
            return RouterResult(
                problem_type=ProblemType.UNSUPPORTED,
                confidence=0.0,
                matched_keywords=generic_matches,
                reason="generic routing requires an objective verb or multiple modeling signals",
            )
    if not any(matches_by_type.values()):
        return RouterResult(
            problem_type=ProblemType.UNSUPPORTED,
            confidence=0.0,
            matched_keywords=[],
            reason="未命中 production、assignment、jobshop、vrp 的明显关键词",
        )

    scores = {
        problem_type: _score(normalized, problem_type, matches)
        for problem_type, matches in matches_by_type.items()
    }
    priority = [
        ProblemType.VRP,
        ProblemType.JOBSHOP,
        ProblemType.ASSIGNMENT,
        ProblemType.PRODUCTION,
        ProblemType.GENERIC_LP_MILP,
    ]
    ordered = sorted(
        scores,
        key=lambda problem_type: (scores[problem_type], -priority.index(problem_type)),
        reverse=True,
    )
    winner = ordered[0]
    second_score = scores[ordered[1]]
    matched = matches_by_type[winner]

    if not matched:
        return RouterResult(
            problem_type=ProblemType.UNSUPPORTED,
            confidence=0.0,
            matched_keywords=[],
            reason="没有足够关键词支持任一问题类型",
        )

    keyword_text = "、".join(matched)
    return RouterResult(
        problem_type=winner,
        confidence=_confidence(scores[winner], second_score, len(matched)),
        matched_keywords=matched,
        reason=f"命中 {winner.value} 相关关键词：{keyword_text}",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Route a Chinese optimization question to a problem type.")
    parser.add_argument("text", nargs="?", help="中文优化问题文本")
    args = parser.parse_args(argv)

    if not args.text:
        parser.print_usage()
        return 2

    result = route_text(args.text)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
