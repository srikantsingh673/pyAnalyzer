from __future__ import annotations

import json
import shutil
import subprocess


def is_available() -> bool:
    return shutil.which("mypy") is not None


def run(file_path: str) -> list[dict]:
    if not is_available():
        return []
    try:
        proc = subprocess.run(
            [
                "mypy",
                "--output=json",
                "--ignore-missing-imports",
                "--no-error-summary",
                "--follow-imports=skip",
                file_path,
            ],
            capture_output=True, text=True, timeout=60,
        )
        issues = []
        for raw in (proc.stdout or "").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
                if obj.get("severity") != "note":
                    issues.append(obj)
            except json.JSONDecodeError:
                pass
        return issues
    except Exception:
        return []
