from __future__ import annotations
from pathlib import Path

_SEVERITY_WEIGHT = {"error": 10, "warning": 4, "info": 1}
_SEV_ORDER = {"error": 0, "warning": 1, "info": 2}


def build_report(
    issues: list[dict],
    metrics: dict,
    source: str,
    file_path: str,
    elapsed: float,
    settings: dict,
) -> dict:
    lines = source.splitlines()
    total_lines = len(lines)
    code_lines = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    blank_lines = sum(1 for ln in lines if not ln.strip())
    comment_lines = total_lines - code_lines - blank_lines

    base_metrics = {
        "Total lines": total_lines,
        "Code lines": code_lines,
        "Blank lines": blank_lines,
        "Comment lines": comment_lines,
        "Analysis time": f"{elapsed}s",
    }
    base_metrics.update(metrics)

    deduction = sum(_SEVERITY_WEIGHT.get(i.get("severity", "info"), 1) for i in issues)
    score = max(0, 100 - deduction)

    counts = {"errors": 0, "warnings": 0, "info": 0}
    for issue in issues:
        sev = issue.get("severity", "info")
        if sev == "error":
            counts["errors"] += 1
        elif sev == "warning":
            counts["warnings"] += 1
        else:
            counts["info"] += 1

    sorted_issues = sorted(
        issues,
        key=lambda i: (_SEV_ORDER.get(i.get("severity", "info"), 2), i.get("line", 0))
    )

    return {
        "summary": {
            "score": score,
            "file": Path(file_path).name,
            "path": file_path,
            **counts,
        },
        "issues": sorted_issues,
        "metrics": base_metrics,
    }
