from __future__ import annotations

import importlib


def test_demo_cases_load_three_stable_cases():
    from nl2opt.ui.demo_cases import load_demo_cases

    cases = load_demo_cases()

    assert [case.case_id for case in cases] == [
        "extractor_production_01",
        "extractor_jobshop_01",
        "extractor_vrp_01",
    ]
    assert {case.category for case in cases} == {"production", "jobshop", "vrp"}
    assert all(case.prompt_zh.strip() for case in cases)


def test_load_final_eval_summary_reads_live_20_result():
    from nl2opt.ui.demo_cases import load_final_eval_summary

    summary = load_final_eval_summary()

    assert summary["found"] is True
    assert summary["provider"] == "deepseek"
    assert summary["model"] == "deepseek-v4-flash"
    assert summary["mock"] is False
    assert summary["prompt_version"] == "v3"
    assert summary["total"] == 20
    assert summary["end_to_end_success"] == 20
    assert summary["failure_breakdown"] == {}


def test_explain_solution_handles_supported_problem_types():
    from nl2opt.ui.explain import explain_solution

    base = {
        "solver_status": "OPTIMAL",
        "objective_value": 123,
        "checker_passed": True,
        "violations": [],
    }

    for problem_type in ["production", "assignment", "jobshop", "vrp"]:
        text = explain_solution(problem_type, base, {"solution": {"x": 1}})
        assert problem_type in text
        assert "123" in text
        assert "checker" in text.lower()


def test_streamlit_app_module_imports_without_running_ui():
    module = importlib.import_module("nl2opt.ui.streamlit_app")

    assert hasattr(module, "main")
    assert hasattr(module, "run_single_problem")


def test_run_single_problem_rejects_missing_client_for_live_path():
    from nl2opt.ui.streamlit_app import run_single_problem

    result = run_single_problem(
        "某工厂生产 A 和 B 两种产品，问如何安排产量使利润最大。",
        prompt_version="v3",
        client=None,
        output_root=None,
    )

    assert result["success"] is False
    assert "client" in result["error"].lower()
