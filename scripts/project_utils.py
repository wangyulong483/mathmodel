# -*- coding: utf-8 -*-
"""Shared paths, configuration, and small utilities for the MathModel toolchain."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = PROJECT_ROOT / "mathmodel.config.json"


def load_config() -> dict[str, Any]:
    """Load the project configuration and apply environment overrides."""
    config: dict[str, Any] = {
        "project_version": "4.1",
        "competition": {},
        "paths": {},
        "ai": {},
    }
    if CONFIG_PATH.exists():
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))

    ai = config.setdefault("ai", {})
    overrides = {
        "provider": os.getenv("MM_AI_PROVIDER"),
        "api_style": os.getenv("MM_AI_API_STYLE"),
        "base_url": os.getenv("MM_AI_BASE_URL"),
        "model": os.getenv("MM_AI_MODEL"),
        "temperature": os.getenv("MM_AI_TEMPERATURE"),
        "timeout_seconds": os.getenv("MM_AI_TIMEOUT"),
    }
    for key, value in overrides.items():
        if value is None or value == "":
            continue
        if key in {"temperature", "timeout_seconds"}:
            value = float(value) if key == "temperature" else int(value)
        ai[key] = value
    return config


def project_path(relative: str) -> Path:
    return PROJECT_ROOT / relative


def configured_path(config: dict[str, Any], key: str, default: str) -> Path:
    return project_path(config.get("paths", {}).get(key, default))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with UTF-8 text handling on Windows and Unix."""
    return subprocess.run(
        args,
        cwd=str(cwd or PROJECT_ROOT),
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture_output,
    )


def parse_markdown_heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2)


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def print_header(title: str) -> None:
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
