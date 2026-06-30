from __future__ import annotations

from typing import Any


PROBLEM_LABELS = {
    "production": "生产计划",
    "assignment": "任务分配",
    "jobshop": "作业车间排产",
    "vrp": "车辆路径配送",
}


def explain_solution(
    problem_type: str,
    pipeline_result: dict[str, Any],
    solver_result: dict[str, Any] | None = None,
) -> str:
    label = PROBLEM_LABELS.get(problem_type, problem_type)
    status = pipeline_result.get("solver_status")
    objective_value = pipeline_result.get("objective_value")
    checker_passed = bool(pipeline_result.get("checker_passed"))
    violations = pipeline_result.get("violations") or []

    lines = [
        f"系统识别为 {problem_type}（{label}）问题。",
        f"OR-Tools 返回状态为 {status}，目标值为 {objective_value}。",
    ]

    if problem_type == "production":
        lines.append("checker 已重新计算资源使用量和目标值，确认生产计划满足资源容量约束。")
    elif problem_type == "assignment":
        lines.append("checker 已验证每个任务只分配一次、员工 capacity 未超限，并重新计算总成本。")
    elif problem_type == "jobshop":
        lines.append("checker 已验证工序先后顺序、机器不重叠、加工时长和 makespan。")
    elif problem_type == "vrp":
        lines.append("checker 已验证车辆从 depot 出发并返回、客户访问唯一性、车辆容量和路线距离。")
    else:
        lines.append("checker 已根据当前 problem_type 执行可用的结果复核。")

    if checker_passed:
        lines.append("checker 结果为 PASS，说明求解结果与当前 schema 支持的约束一致。")
    else:
        lines.append("checker 结果为 FAIL，需要查看 violations。")
        if violations:
            lines.append("主要 violations: " + "; ".join(str(item) for item in violations))

    if solver_result and solver_result.get("solution"):
        lines.append("页面中的 Solver Result 展示了原始 solution JSON，可用于查看变量、路线或排程细节。")

    lines.append("该解释只基于结构化 ProblemSpec 和 solver/checker 输出，不重新猜测题意。")
    return "\n\n".join(lines)
