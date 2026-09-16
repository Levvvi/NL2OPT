from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:  # Streamlit is optional for import smoke tests; installed app runs use the real package.
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - exercised only before optional dependency install.
    st = None  # type: ignore[assignment]

from nl2opt.agents.extractor import ExtractorResult, extract_problem_spec
from nl2opt.agents.llm_client import DeepSeekClient, LLMClient
from nl2opt.config import get_deepseek_api_key_source
from nl2opt.pipeline import PipelineResult, run_problem_spec
from nl2opt.runtime.runner import load_solver_result
from nl2opt.ui.demo_cases import DemoCase, load_demo_cases, load_final_eval_summary
from nl2opt.ui.explain import explain_solution


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "streamlit_demo"
PROMPT_VERSION = "v3"


def _safe_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    json_path = Path(path)
    if not json_path.exists():
        return None
    data = json.loads(json_path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _pipeline_to_dict(result: PipelineResult) -> dict[str, Any]:
    return result.to_report_dict()


def _new_output_dir(output_root: Path, problem_type: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"{problem_type}_{stamp}"


def run_single_problem(
    prompt_zh: str,
    prompt_version: str = PROMPT_VERSION,
    client: LLMClient | None = None,
    output_root: Path | None = DEFAULT_OUTPUT_ROOT,
    timeout_sec: int = 20,
) -> dict[str, Any]:
    if client is None:
        return {
            "success": False,
            "error": "LLM client is required for live extraction.",
            "failure_stage": "configuration_error",
            "extractor_result": None,
            "problem_spec": None,
            "pipeline_result": None,
            "solver_result": None,
            "checker_report": None,
            "explanation": None,
        }

    extraction = extract_problem_spec(
        prompt_zh,
        problem_type=None,
        client=client,
        prompt_version=prompt_version,
    )

    if not extraction.success or extraction.spec is None:
        return {
            "success": False,
            "error": extraction.error or "extractor failed",
            "failure_stage": "extraction_error",
            "extractor_result": asdict(extraction),
            "problem_spec": extraction.spec_dict,
            "pipeline_result": None,
            "solver_result": None,
            "checker_report": None,
            "explanation": None,
        }

    output_dir = _new_output_dir(Path(output_root or DEFAULT_OUTPUT_ROOT), extraction.problem_type)
    pipeline_result = run_problem_spec(extraction.spec, output_dir, timeout_sec=timeout_sec)
    pipeline_dict = _pipeline_to_dict(pipeline_result)
    solver_result = _safe_json(pipeline_result.solution_path)

    checker_report = pipeline_result.checker_report
    if pipeline_result.checker_passed:
        explanation = explain_solution(extraction.problem_type, pipeline_dict, solver_result)
    elif checker_report is None:
        explanation = f"运行已停止，尚未完成结果复核：{pipeline_result.error}"
    else:
        explanation = "结果复核未通过：" + "; ".join(pipeline_result.violations)

    return {
        "success": bool(extraction.success and pipeline_result.checker_passed),
        "error": pipeline_result.error,
        "failure_stage": pipeline_result.failure_stage,
        "extractor_result": {
            "success": extraction.success,
            "problem_type": extraction.problem_type,
            "provider": extraction.provider,
            "model": extraction.model,
            "prompt_version": extraction.prompt_version,
            "validation_errors": extraction.validation_errors,
            "error": extraction.error,
        },
        "problem_spec": extraction.spec_dict,
        "pipeline_result": pipeline_dict,
        "solver_result": solver_result,
        "checker_report": checker_report,
        "explanation": explanation,
    }


def _demo_options(cases: list[DemoCase]) -> dict[str, DemoCase | None]:
    return {
        "production": next(case for case in cases if case.category == "production"),
        "jobshop": next(case for case in cases if case.category == "jobshop"),
        "vrp": next(case for case in cases if case.category == "vrp"),
        "custom": None,
    }


def _render_sidebar() -> tuple[str, dict[str, Any], bool]:
    summary = load_final_eval_summary()
    key_source = get_deepseek_api_key_source()
    key_available = key_source != "missing"

    st.sidebar.header("Live Eval")
    st.sidebar.metric("Final live eval", f"{summary.get('end_to_end_success') or '-'} / {summary.get('total') or '-'}")
    st.sidebar.write(f"provider: `{summary.get('provider') or 'deepseek'}`")
    st.sidebar.write(f"model: `{summary.get('model') or 'deepseek-v4-flash'}`")
    st.sidebar.write(f"prompt_version: `{summary.get('prompt_version') or PROMPT_VERSION}`")
    st.sidebar.write(f"mock: `{summary.get('mock')}`")
    st.sidebar.write(f"API key: `{'available' if key_available else 'missing'}`")
    if not summary.get("found"):
        st.sidebar.warning("final eval summary not found")

    selected = st.sidebar.selectbox("Demo case", ["production", "jobshop", "vrp", "custom"])
    return selected, summary, key_available


def main() -> None:
    if st is None:
        raise RuntimeError("Streamlit is not installed. Run `python -m pip install -e \".[dev]\"` first.")

    st.set_page_config(page_title="NL2OPT", layout="wide")
    st.title("NL2OPT: 中文自然语言到优化模型的受控工作流")
    st.caption("中文输入 -> ProblemSpec -> OR-Tools 求解 -> checker 校验 -> 中文解释")

    selected, summary, key_available = _render_sidebar()
    cases = load_demo_cases()
    options = _demo_options(cases)
    demo_case = options[selected]

    default_text = demo_case.prompt_zh if demo_case else ""
    prompt_zh = st.text_area("中文问题", value=default_text, height=180)

    metadata = {
        "selected_case": selected,
        "case_id": demo_case.case_id if demo_case else None,
        "difficulty": demo_case.difficulty if demo_case else None,
        "expected_problem_type": demo_case.expected_problem_type if demo_case else None,
        "final_eval_summary_path": summary.get("path"),
    }

    if st.button("Run", type="primary"):
        if not prompt_zh.strip():
            st.error("请输入中文问题。")
        elif not key_available:
            st.error("DeepSeek key missing，可先查看预置 demo 文本，但不能运行 live extractor。")
        else:
            with st.status("running", expanded=True) as status:
                st.write("Calling DeepSeek extractor...")
                client = DeepSeekClient()
                result = run_single_problem(prompt_zh, prompt_version=PROMPT_VERSION, client=client)
                status.update(
                    label="success" if result["success"] else "failed",
                    state="complete" if result["success"] else "error",
                )

            if result["success"]:
                st.success("Pipeline completed and checker passed.")
            else:
                st.error(result["error"] or "Pipeline failed.")

            tabs = st.tabs([
                "输入问题",
                "ProblemSpec JSON",
                "Solver Result",
                "Checker Report",
                "中文解释",
                "Logs / Metadata",
            ])
            with tabs[0]:
                st.write(prompt_zh)
            with tabs[1]:
                st.json(result.get("problem_spec") or {})
            with tabs[2]:
                st.json(result.get("solver_result") or {})
            with tabs[3]:
                st.json(result.get("checker_report") or {})
            with tabs[4]:
                st.write(result.get("explanation") or "No explanation available.")
            with tabs[5]:
                st.json(
                    {
                        "metadata": metadata,
                        "extractor_result": result.get("extractor_result"),
                        "pipeline_result": result.get("pipeline_result"),
                    }
                )
    else:
        st.info("选择 demo case 或粘贴 custom 中文问题，然后点击 Run。custom 输入会调用 DeepSeek API。")


if __name__ == "__main__":
    main()
