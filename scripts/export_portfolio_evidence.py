"""Export actual deterministic checks and existing benchmark CSV facts for the site.

No model calls, secrets, machine paths, or unpublished failure archives are exported.
Run from the repository with: uv run python scripts/export_portfolio_evidence.py
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
import subprocess
import tempfile

from nl2opt.checkers.production_checker import check_production_solution
from nl2opt.pipeline import load_problem_spec, run_problem_spec
from nl2opt.schemas import ProductionProblemSpec, SolverResult, SolverStatus

ROOT = Path(__file__).resolve().parents[1]
RUN_IDS = ("public-20260710-off", "public-20260711-on-rerun")
PROMPT_ZH = (
    "工厂生产 A、B 两种产品。A 每件利润 40 元，B 每件利润 30 元。"
    "A 每件需要工时 2、材料 1；B 每件需要工时 1、材料 2。"
    "工时上限 100，材料上限 80。产量为非负整数，求最大利润。"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def public_pipeline(report: dict) -> dict:
    # Whitelist portable fields instead of attempting to redact raw logs/paths.
    fields = (
        "problem_id", "problem_type", "returncode", "timed_out", "solver_status",
        "objective_value", "checker_passed", "violations", "runtime_sec", "error",
        "failure_stage", "checker_report",
    )
    return {name: report.get(name) for name in fields}


def public_text(value: str) -> str:
    value = re.sub(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\)[^\s\"']+", "<local-path>", value)
    value = re.sub(r"(?i)(?:bearer\s+\S+|sk-[A-Za-z0-9_-]{10,})", "<redacted>", value)
    return value[:2000]


def benchmark_index() -> tuple[list[dict], list[dict]]:
    runs, summaries = [], []
    for run_id in RUN_IDS:
        directory = ROOT / "reports" / "artifacts" / run_id
        with (directory / "results.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        manifest = json.loads((directory / "run_manifest.json").read_text())
        failures = [row for row in rows if row["passed_1e_6"].lower() != "true"]
        categories = dict(sorted(Counter(row["failure_category"] or "unclassified" for row in failures).items()))
        records = []
        for row in failures:
            records.append({
                "id": f'{run_id}:{row["dataset"]}:{row["item_id"]}:{row["track"]}:{row["repetition"]}',
                "case_id": row["item_id"],
                "dataset": row["dataset"],
                "language": row["track"],
                "repeat": int(row["repetition"]),
                "status": row["status"],
                "failure_category": row["failure_category"] or "unclassified",
                "judgment_reason": public_text(row["judgment_reason"]),
                "error": public_text(row["error"]),
                "model": row["extractor_model"],
                "runtime_sec": round(float(row["wall_sec"]), 3) if row["wall_sec"] else None,
                "evaluated_at": row["evaluated_at"],
                "checker_passed": row["checker_passed"].lower() == "true",
                "checker_retried": row["checker_retried"].lower() == "true",
                "full_artifact_available": False,
            })
        summary = {
            "id": run_id,
            "label": f'公开基准 · checker retry {manifest["checker_retry"]}',
            "total": len(rows),
            "passed": len(rows) - len(failures),
            "failures": len(failures),
            "accuracy_pct": round(100 * (len(rows) - len(failures)) / len(rows), 1),
            "checker_retry": manifest["checker_retry"],
            "checker_retries": sum(row["checker_retried"].lower() == "true" for row in rows),
            "source_csv": f"reports/artifacts/{run_id}/results.csv",
            "source_csv_sha256": sha256(directory / "results.csv"),
            "completed_at": manifest["completed_at"],
            "scope": "345 个原始题（NL4Opt 245 + IndustryOR 100）× 英语/中文 × 3 次重复 = 2,070 次尝试",
            "categories": categories,
            "full_artifact_available": False,
        }
        runs.append({**summary, "records": records})
        summaries.append(summary)
    return runs, summaries


def source_metadata() -> dict:
    paths = sorted({*ROOT.glob("src/nl2opt/**/*.py"), *ROOT.glob("src/nl2opt/**/*.j2"), ROOT / "scripts/export_portfolio_evidence.py", ROOT / "examples/specs/production_basic.json"})
    per_file = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    digest = hashlib.sha256(json.dumps(per_file, sort_keys=True).encode()).hexdigest()
    return {
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_modified": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "source_sha256": digest,
        "source_files_sha256": per_file,
        "lock_sha256": sha256(ROOT / "uv.lock"),
        "python": platform.python_version(),
        "dependencies": {name: version(name) for name in ("ortools", "pydantic", "jinja2", "openai", "pytest")},
        "model_called": False,
        "command": "uv run python scripts/export_portfolio_evidence.py",
    }


def build_cases() -> list[dict]:
    spec = load_problem_spec(ROOT / "examples/specs/production_basic.json")
    cases = []
    common = {
        "prompt_zh": PROMPT_ZH,
        "prompt_provenance": "人工转述已有 JSON 样例；本次未调用 LLM 抽取。",
        "problem_spec": spec.model_dump(mode="json"),
    }
    with tempfile.TemporaryDirectory(prefix="nl2opt-evidence-") as temp:
        pipeline = run_problem_spec(spec, Path(temp) / "success", timeout_sec=30)
        if not pipeline.checker_passed:
            raise RuntimeError(f"Production baseline failed: {pipeline.violations}")
        result = SolverResult.model_validate_json(Path(pipeline.solution_path).read_text())
        checker = check_production_solution(spec, result)
        if not checker.passed or checker.computed_objective != 2200:
            raise RuntimeError("Production baseline no longer matches documented evidence")
        cases.append({
            **common,
            "id": "production-success",
            "label": "成功案例：求解后独立复核",
            "kind": "deterministic_run",
            "description": "实际运行固定模板与 OR-Tools，随后由 production checker 重算资源和利润。",
            "solver_result": result.model_dump(mode="json"),
            "checker_report": asdict(checker),
            "pipeline_result": public_pipeline(pipeline.to_report_dict()),
            "provenance": {"model_called": False, "solver_called": True, "checker_called": True, "fault_injected": False},
        })
        for case_id, label, description, quantities, objective in (
            ("production-capacity-failure", "故障注入：资源超限", "人工将产量改为 A=41、B=20；真实 checker 应发现工时 102>100、材料 81>80。", {"A": 41, "B": 20}, 2240),
            ("production-integrality-failure", "故障注入：小数产量", "人工构造 A=0.5、B=0、利润=20；即便资源未超限，真实 checker 仍须拒绝非整数产量。", {"A": 0.5, "B": 0}, 20),
        ):
            injected = SolverResult(status=SolverStatus.FEASIBLE, objective_value=objective, solution={"quantities": quantities}, runtime_sec=0, solver="fault_injection_no_solver_call")
            checked = check_production_solution(spec, injected)
            if checked.passed:
                raise RuntimeError(f"Fault injection was incorrectly accepted: {case_id}")
            cases.append({
                **common, "id": case_id, "label": label, "kind": "fault_injection",
                "description": description,
                "solver_result": injected.model_dump(mode="json"),
                "checker_report": asdict(checked),
                "pipeline_result": {"failure_stage": "checker", "checker_passed": False, "violations": checked.violations, "solver_executed": False},
                "provenance": {"model_called": False, "solver_called": False, "checker_called": True, "fault_injected": True},
            })
        missing_data = spec.model_dump(mode="json")
        missing_data["missing_fields"] = ["material.capacity"]
        missing = ProductionProblemSpec.model_validate(missing_data)
        missing_run = run_problem_spec(missing, Path(temp) / "missing", timeout_sec=30)
        if missing_run.checker_passed or missing_run.code_path is not None:
            raise RuntimeError("Missing-field gate failed to stop before solver generation")
        cases.append({
            **common,
            "problem_spec": missing.model_dump(mode="json"),
            "id": "production-missing-fields",
            "label": "故障注入：缺参前检拒绝",
            "kind": "fault_injection",
            "description": "人工将 material.capacity 标为缺参（保留的数值视为占位值），由真实 pipeline 在生成求解代码前拒绝。",
            "solver_result": None,
            "checker_report": None,
            "pipeline_result": public_pipeline(missing_run.to_report_dict()),
            "provenance": {"model_called": False, "solver_called": False, "checker_called": False, "fault_injected": True},
        })
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports/portfolio")
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc).isoformat()
    source = source_metadata()
    cases = build_cases()
    runs, benchmarks = benchmark_index()
    evidence = {
        "schema_version": 1,
        "generated_at": timestamp,
        "source": source,
        "limitations": [
            "前检与后检依赖已抽取的 ProblemSpec，不能证明自然语言语义全部正确。",
            "checker 通过不等于独立证明全局最优。",
            "故障注入用于展示真实检查机制，不代表历史模型实际输出。",
            "本导出脚本未调用真实模型；历史 20/20、公开基准和另行记录的 live smoke 与这些确定性演示分别呈现。",
        ],
        "cases": cases,
        "benchmarks": benchmarks,
    }
    index = {
        "schema_version": 1, "generated_at": timestamp,
        "provenance": "从已公开 CSV 提取全部失败行的白名单字段；不包含或链接未公开完整失败档案。",
        "runs": runs,
    }
    write_json(args.output_dir / "evidence.json", evidence)
    write_json(args.output_dir / "failure-index.json", index)
    print(json.dumps({"output_dir": str(args.output_dir), "cases": len(cases), "benchmark_failures": [len(run["records"]) for run in runs], "source_sha256": source["source_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
