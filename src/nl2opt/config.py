from __future__ import annotations

import argparse
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MISSING_PLACEHOLDERS = {
    "",
    "your_deepseek_api_key_here",
    "your_key_here",
}


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if (
        (cleaned.startswith('"') and cleaned.endswith('"'))
        or (cleaned.startswith("'") and cleaned.endswith("'"))
    ):
        cleaned = cleaned[1:-1].strip()
    if cleaned in MISSING_PLACEHOLDERS:
        return None
    return cleaned


def _read_env_file_value(path: Path, name: str) -> str | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key == name:
            return _clean_value(value)
    return None


def get_config_value(name: str, project_root: Path | None = None) -> str | None:
    process_value = _clean_value(os.getenv(name))
    if process_value:
        return process_value

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    for filename in (".env.local", ".env"):
        value = _read_env_file_value(root / filename, name)
        if value:
            return value
    return None


def get_deepseek_api_key(project_root: Path | None = None) -> str | None:
    return get_config_value("DEEPSEEK_API_KEY", project_root=project_root)


def get_deepseek_api_key_source(project_root: Path | None = None) -> str:
    if _clean_value(os.getenv("DEEPSEEK_API_KEY")):
        return "process_env"

    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    if _read_env_file_value(root / ".env.local", "DEEPSEEK_API_KEY"):
        return "env_local"
    if _read_env_file_value(root / ".env", "DEEPSEEK_API_KEY"):
        return "env"
    return "missing"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely report NL2OPT configuration visibility.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)

    print(f"DEEPSEEK_API_KEY_SOURCE={get_deepseek_api_key_source(args.project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
