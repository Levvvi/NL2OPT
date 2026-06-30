from __future__ import annotations

import json
from typing import Any

from nl2opt.schemas import ProblemType


V2_COMMON_RULES = [
    "数字必须输出为 JSON number，不要输出“40元”这种字符串。",
    "problem_type 必须和输入 problem_type 完全一致。",
    "不要新增 schema 之外字段。",
    "题目没给的信息放入 missing_fields 或 assumptions，不要编造。",
    "所有实体名必须在后续矩阵字段中保持一致。",
]


V2_TYPE_HINTS: dict[ProblemType, list[str]] = {
    ProblemType.PRODUCTION: [
        "products 必须包含利润字段。",
        "resources 必须包含 capacity。",
        "consumption 必须覆盖每个出现的产品-资源消耗。",
        "如果题目说“产量”，默认变量是非负整数。",
    ],
    ProblemType.ASSIGNMENT: [
        "employees 和 tasks 名称必须和 costs 中一致。",
        "costs 可以是稀疏矩阵。",
        "每个 task 至少要有一个可分配 employee。",
        "capacity 表示最多可承担任务数。",
    ],
    ProblemType.JOBSHOP: [
        "operations 顺序就是加工先后顺序。",
        "machine 必须来自 machines。",
        "duration 必须是正整数。",
        "objective 必须是 minimize makespan。",
    ],
    ProblemType.VRP: [
        "depot、customers、vehicles 必须分开。",
        "distance_matrix 必须包含 depot 和全部 customers 的完整行列。",
        "demand 必须是 number。",
        "本 MVP 不支持 dropped customers、time windows、多仓库。",
    ],
}


V3_COMMON_RULES = [
    "Return exactly one JSON object. Do not wrap it in markdown or a code fence.",
    "Use only field names that appear in the provided JSON schema.",
    "Do not add fields that are not in the JSON schema.",
    "The problem_type value must exactly equal the requested problem_type.",
    "All numbers must be JSON numbers, not strings with units such as '10 hours' or '30 yuan'.",
    "Do not solve the optimization problem and do not output solution fields.",
    "If required numeric data is missing from the text, record the field path in missing_fields; do not invent a value and do not use 0 as a placeholder.",
    "Entity names must be stable across lists and matrix fields.",
]


V3_TYPE_HINTS: dict[ProblemType, list[str]] = {
    ProblemType.PRODUCTION: [
        "Use fields: problem_id, problem_type, objective, products, resources, consumption, assumptions, missing_fields.",
        "objective should normally be {'sense': 'maximize', 'name': 'profit'} for profit maximization.",
        "products must be a list of objects like {'name': 'A', 'profit': 40}.",
        "resources must be a list of objects like {'name': 'labor', 'capacity': 100}.",
        "consumption must be nested by product then resource: {'A': {'labor': 2, 'material': 1}}.",
        "Do not describe resource consumption in natural language.",
        "If the text does not give resource capacities or product-resource consumption values, list those exact paths in missing_fields.",
    ],
    ProblemType.ASSIGNMENT: [
        "Use fields: problem_id, problem_type, objective, employees, tasks, costs, assumptions, missing_fields.",
        "objective should normally be exactly {'sense': 'minimize', 'name': 'cost'}.",
        "employees must be a list of objects like {'name': 'Alice', 'capacity': 2}.",
        "tasks must be a list of objects like {'name': 'T1'}.",
        "costs must be an object of objects keyed by employee then task: {'Alice': {'T1': 8, 'T2': 6}}.",
        "Do not output workers, cost_matrix, assignments, or solution.",
        "Every task must appear under at least one employee in costs if a cost is provided in the text.",
        "If a task cost is not given, put that employee-task cost path in missing_fields; do not invent or use 0.",
    ],
    ProblemType.JOBSHOP: [
        "Use fields: problem_id, problem_type, objective, machines, jobs, assumptions, missing_fields.",
        "objective must be exactly {'sense': 'minimize', 'name': 'makespan'}.",
        "machines must be a list of objects like {'name': 'M1'}.",
        "jobs must be a list of objects like {'name': 'J1', 'operations': [{'machine': 'M1', 'duration': 3}]}.",
        "operations must appear in the same order as the text describes the processing sequence.",
        "Each operation must contain only machine and duration.",
        "duration must be a positive integer JSON number.",
        "Do not combine machine names and processing times into one string.",
    ],
    ProblemType.VRP: [
        "Use fields: problem_id, problem_type, objective, depot, vehicles, customers, distance_matrix, assumptions, missing_fields.",
        "objective must be exactly {'sense': 'minimize', 'name': 'distance'}.",
        "vehicles must be a list of objects like {'name': 'V1', 'capacity': 15}.",
        "customers must be a list of objects like {'name': 'C1', 'demand': 4}.",
        "distance_matrix must be a complete nested object with one row and one column for depot and every customer.",
        "Each distance_matrix row must include the depot and all customers; diagonal distances must be 0.",
        "Do not output vehicle_count, vehicle_capacity, demands, dropped_customers, routes, or solution.",
        "This MVP does not support time windows, dropped visits, multiple depots, pickup-delivery, or route penalties.",
    ],
}


def _numbered(lines: list[str], start: int = 1) -> str:
    return "\n".join(f"{index}. {line}" for index, line in enumerate(lines, start=start))


def _v1_prompts(text: str, problem_type: ProblemType, schema_json: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "你是中文优化建模信息抽取器。"
        "你的任务是从中文问题中抽取实体、参数、目标和约束，输出符合指定 schema 的 ProblemSpec JSON。"
        "你只负责抽取结构化数据，不负责求解，不编写 OR-Tools 代码。"
        "只输出 JSON 对象，不要输出 markdown、解释文字或多余前后缀。"
    )
    schema_text = json.dumps(schema_json, ensure_ascii=False, indent=2)
    user_prompt = (
        f"原始中文问题：\n{text}\n\n"
        f"problem_type：{problem_type.value}\n\n"
        f"目标 JSON schema：\n{schema_text}\n\n"
        "输出要求：\n"
        "1. 输出必须是单个 JSON 对象。\n"
        "2. problem_type 必须与给定 problem_type 一致。\n"
        "3. 缺失但可合理默认的字段放入 assumptions；无法确定的字段放入 missing_fields。\n"
        "4. 不要求解问题，不要输出 solution。"
    )
    return system_prompt, user_prompt


def _v2_prompts(text: str, problem_type: ProblemType, schema_json: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "你是中文优化建模信息抽取器。"
        "你只负责把中文问题抽取成符合 schema 的 ProblemSpec JSON，不负责求解，不编写 OR-Tools 代码。"
        "只输出 JSON 对象，不要输出 markdown、解释文字、代码块或多余前后缀。"
        "如果无法确定某个字段，使用 missing_fields 或 assumptions 记录。"
    )
    schema_text = json.dumps(schema_json, ensure_ascii=False, indent=2)
    type_hints = V2_TYPE_HINTS.get(problem_type, [])
    user_prompt = (
        f"原始中文问题：\n{text}\n\n"
        f"problem_type：{problem_type.value}\n\n"
        f"目标 JSON schema：\n{schema_text}\n\n"
        "通用抽取规则：\n"
        f"{_numbered(V2_COMMON_RULES)}\n\n"
        f"{problem_type.value} schema-specific hints：\n"
        f"{_numbered(type_hints)}\n\n"
        "输出要求：\n"
        "1. 输出必须是单个 JSON 对象。\n"
        "2. 只输出 JSON，不要输出 markdown 或解释。\n"
        "3. 不要求解问题，不要输出 solution。"
    )
    return system_prompt, user_prompt


def _v3_prompts(text: str, problem_type: ProblemType, schema_json: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "You are an information extraction component for Chinese optimization modeling. "
        "Your only job is to convert the user's problem statement into a ProblemSpec JSON object "
        "that validates against the provided JSON schema. "
        "Return exactly one JSON object. Do not output markdown, explanations, code fences, solver code, or a solution. "
        "The word json is intentionally included because the API is using JSON output mode."
    )
    schema_text = json.dumps(schema_json, ensure_ascii=False, indent=2)
    type_hints = V3_TYPE_HINTS.get(problem_type, [])
    user_prompt = (
        f"Original problem text:\n{text}\n\n"
        f"Requested problem_type: {problem_type.value}\n\n"
        f"Target JSON schema:\n{schema_text}\n\n"
        "Common extraction rules:\n"
        f"{_numbered(V3_COMMON_RULES)}\n\n"
        f"{problem_type.value} schema-specific output requirements:\n"
        f"{_numbered(type_hints)}\n\n"
        "Output contract:\n"
        "1. Return exactly one JSON object.\n"
        "2. Use enum values exactly as defined by the schema, for example maximize/minimize and production/assignment/jobshop/vrp.\n"
        "3. Keep missing_fields and assumptions as JSON arrays of strings.\n"
        "4. Keep object/list/matrix shapes exactly aligned with the schema.\n"
        "5. Do not include any explanation outside the JSON object.\n"
    )
    return system_prompt, user_prompt


def build_extractor_prompt(
    text: str,
    problem_type: ProblemType,
    schema_json: dict[str, Any],
    prompt_version: str = "v2",
) -> tuple[str, str]:
    if prompt_version == "v1":
        return _v1_prompts(text, problem_type, schema_json)
    if prompt_version == "v2":
        return _v2_prompts(text, problem_type, schema_json)
    if prompt_version == "v3":
        return _v3_prompts(text, problem_type, schema_json)
    raise ValueError(f"unsupported prompt_version: {prompt_version}")
