from __future__ import annotations

import json
import shutil
import subprocess


def is_available() -> bool:
    return shutil.which("radon") is not None


def run_cc(file_path: str) -> list[dict]:
    if not is_available():
        return []
    try:
        proc = subprocess.run(
            ["radon", "cc", "--json", "--show-complexity", "--min=A", file_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
        # radon keys the output by file path
        return data.get(file_path) or next(iter(data.values()), [])
    except Exception:
        return []
