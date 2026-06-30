__all__ = [
    "evaluate_mock_extractor_cases",
    "evaluate_deepseek_extractor_cases",
    "evaluate_router_cases",
    "analyze_deepseek_eval_outputs",
    "load_case_artifacts",
    "load_extractor_cases",
    "load_router_cases",
    "write_failure_report",
]


def __getattr__(name: str):
    if name in {"evaluate_router_cases", "load_router_cases"}:
        from nl2opt.eval.router_eval import evaluate_router_cases, load_router_cases

        exports = {
            "evaluate_router_cases": evaluate_router_cases,
            "load_router_cases": load_router_cases,
        }
        return exports[name]
    if name in {"evaluate_deepseek_extractor_cases", "evaluate_mock_extractor_cases", "load_extractor_cases"}:
        from nl2opt.eval.extractor_eval import (
            evaluate_deepseek_extractor_cases,
            evaluate_mock_extractor_cases,
            load_extractor_cases,
        )

        exports = {
            "evaluate_deepseek_extractor_cases": evaluate_deepseek_extractor_cases,
            "evaluate_mock_extractor_cases": evaluate_mock_extractor_cases,
            "load_extractor_cases": load_extractor_cases,
        }
        return exports[name]
    if name in {"analyze_deepseek_eval_outputs", "load_case_artifacts", "write_failure_report"}:
        from nl2opt.eval.failure_analysis import (
            analyze_deepseek_eval_outputs,
            load_case_artifacts,
            write_failure_report,
        )

        exports = {
            "analyze_deepseek_eval_outputs": analyze_deepseek_eval_outputs,
            "load_case_artifacts": load_case_artifacts,
            "write_failure_report": write_failure_report,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
