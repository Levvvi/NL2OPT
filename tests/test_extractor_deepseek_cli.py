from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_SPEC_PATH = ROOT / "examples" / "specs" / "production_basic.json"


def test_extractor_cli_deepseek_missing_key_exits_nonzero(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.extractor",
            "某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大",
            "--provider",
            "deepseek",
            "--problem-type",
            "production",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "DEEPSEEK_API_KEY" in completed.stdout


def test_extractor_cli_provider_mock_still_works():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.extractor",
            "--case-id",
            "extractor_production_01",
            "--provider",
            "mock",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["provider"] == "mock"


def test_extractor_cli_mock_spec_still_works():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "nl2opt.agents.extractor",
            "某工厂生产 A 和 B 两种产品，工时和原料有限，问如何安排产量使利润最大？",
            "--provider",
            "mock",
            "--problem-type",
            "production",
            "--mock-spec",
            str(PRODUCTION_SPEC_PATH),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["success"] is True
    assert payload["problem_type"] == "production"
    assert payload["problem_id"] == "production_basic"
