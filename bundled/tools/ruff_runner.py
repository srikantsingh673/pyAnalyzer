from __future__ import annotations

import json
import shutil
import subprocess

_SELECT = "E,W,F,I,D,B,ANN,PD"
_IGNORE = "D203,D212,ANN101,ANN102,ANN401,D401"

_cache: dict[str, list[dict]] = {}


def is_available() -> bool:
    return shutil.which("ruff") is not None


def get(file_path: str, settings: dict) -> list[dict]:
    if file_path not in _cache:
        _cache[file_path] = _run(file_path, settings)
    return _cache[file_path]


def filter_codes(issues: list[dict], *prefixes: str) -> list[dict]:
    return [i for i in issues if any(i.get("code", "").startswith(p) for p in prefixes)]


def _run(file_path: str, settings: dict) -> list[dict]:
    max_line = settings.get("maxLineLength", 88)
    cmd = [
        "ruff", "check",
        "--output-format=json",
        f"--select={_SELECT}",
        f"--ignore={_IGNORE}",
        f"--line-length={max_line}",
        "--no-cache",
        file_path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(proc.stdout) if proc.stdout.strip() else []
    except Exception:
        return []
