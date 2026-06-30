from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_get_deepseek_api_key_prefers_process_env(monkeypatch, tmp_path):
    from nl2opt.config import get_deepseek_api_key, get_deepseek_api_key_source

    (tmp_path / ".env.local").write_text("DEEPSEEK_API_KEY=file-key\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "process-key")

    assert get_deepseek_api_key(tmp_path) == "process-key"
    assert get_deepseek_api_key_source(tmp_path) == "process_env"


def test_get_deepseek_api_key_reads_env_local(monkeypatch, tmp_path):
    from nl2opt.config import get_deepseek_api_key, get_deepseek_api_key_source

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text("DEEPSEEK_API_KEY=local-key\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=env-key\n", encoding="utf-8")

    assert get_deepseek_api_key(tmp_path) == "local-key"
    assert get_deepseek_api_key_source(tmp_path) == "env_local"


def test_get_deepseek_api_key_falls_back_to_env(monkeypatch, tmp_path):
    from nl2opt.config import get_deepseek_api_key, get_deepseek_api_key_source

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY='env-key'\n", encoding="utf-8")

    assert get_deepseek_api_key(tmp_path) == "env-key"
    assert get_deepseek_api_key_source(tmp_path) == "env"


def test_get_deepseek_api_key_missing(monkeypatch, tmp_path):
    from nl2opt.config import get_deepseek_api_key, get_deepseek_api_key_source

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    assert get_deepseek_api_key(tmp_path) is None
    assert get_deepseek_api_key_source(tmp_path) == "missing"


def test_config_cli_does_not_print_secret(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "super-secret-value")
    completed = subprocess.run(
        [sys.executable, "-m", "nl2opt.config"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DEEPSEEK_API_KEY_SOURCE=process_env" in completed.stdout
    assert "super-secret-value" not in completed.stdout
