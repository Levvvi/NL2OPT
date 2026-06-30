from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_cli_runs_production_basic(tmp_path):
    spec_path = ROOT / "examples" / "specs" / "production_basic.json"
    output_dir = tmp_path / "pipeline_cli"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.pipeline",
            str(spec_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "problem_id: production_basic" in completed.stdout
    assert "checker_passed: True" in completed.stdout
    assert (output_dir / "pipeline_report.json").exists()


def test_run_all_basic_script(tmp_path):
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "run_all_basic.py"),
            "--output-root",
            str(tmp_path / "pipeline"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "production_basic" in completed.stdout
    assert "assignment_basic" in completed.stdout
    assert "jobshop_basic" in completed.stdout
    assert "vrp_basic" in completed.stdout
    assert "PASS" in completed.stdout
    assert (tmp_path / "pipeline" / "vrp_basic" / "pipeline_report.json").exists()
