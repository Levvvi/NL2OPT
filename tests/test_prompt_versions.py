from __future__ import annotations


def test_build_extractor_prompt_v1_still_works():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    system_prompt, user_prompt = build_extractor_prompt(
        "某工厂生产 A 和 B 两种产品。",
        ProblemType.PRODUCTION,
        {"type": "object"},
        prompt_version="v1",
    )

    assert "JSON" in system_prompt
    assert "problem_type" in user_prompt
    assert "production" in user_prompt


def test_build_extractor_prompt_v2_contains_json_only_instruction():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    system_prompt, user_prompt = build_extractor_prompt(
        "某工厂生产 A 和 B 两种产品。",
        ProblemType.PRODUCTION,
        {"type": "object"},
    )

    combined = system_prompt + "\n" + user_prompt
    assert "只输出 JSON" in combined
    assert "不要输出 markdown" in combined
    assert "JSON number" in combined
    assert "不要新增 schema 之外字段" in combined


def test_build_extractor_prompt_v2_contains_production_hints():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    _, user_prompt = build_extractor_prompt("生产问题", ProblemType.PRODUCTION, {})

    assert "products 必须包含利润字段" in user_prompt
    assert "resources 必须包含 capacity" in user_prompt
    assert "consumption 必须覆盖" in user_prompt


def test_build_extractor_prompt_v2_contains_assignment_hints():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    _, user_prompt = build_extractor_prompt("任务分配问题", ProblemType.ASSIGNMENT, {})

    assert "employees 和 tasks 名称必须和 costs 中一致" in user_prompt
    assert "costs 可以是稀疏矩阵" in user_prompt
    assert "capacity 表示最多可承担任务数" in user_prompt


def test_build_extractor_prompt_v2_contains_jobshop_hints():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    _, user_prompt = build_extractor_prompt("排产问题", ProblemType.JOBSHOP, {})

    assert "operations 顺序就是加工先后顺序" in user_prompt
    assert "duration 必须是正整数" in user_prompt
    assert "objective 必须是 minimize makespan" in user_prompt


def test_build_extractor_prompt_v2_contains_vrp_hints():
    from nl2opt.agents.prompts import build_extractor_prompt
    from nl2opt.schemas import ProblemType

    _, user_prompt = build_extractor_prompt("配送问题", ProblemType.VRP, {})

    assert "depot、customers、vehicles 必须分开" in user_prompt
    assert "distance_matrix 必须包含 depot 和全部 customers 的完整行列" in user_prompt
    assert "本 MVP 不支持 dropped customers" in user_prompt
