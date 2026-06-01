from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import radon_runner

_RANK_LABEL = {
    "A": "simple (low risk)",
    "B": "manageable",
    "C": "complex (medium risk)",
    "D": "high risk",
    "E": "very high risk",
    "F": "untestable",
}

_BRANCH_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.Assert, ast.comprehension,
)


def run(tree: ast.AST, settings: dict, file_path: str = "") -> dict:
    if file_path and radon_runner.is_available():
        return _from_radon(file_path, settings)
    return _fallback(tree, settings)


def _from_radon(file_path: str, settings: dict) -> dict:
    max_cc = settings.get("maxComplexity", 10)
    blocks = radon_runner.run_cc(file_path)
    issues: list[dict] = []
    complexities: list[int] = []

    for block in blocks:
        cc = block.get("complexity", 1)
        rank = block.get("rank", "A")
        name = block.get("name", "?")
        lineno = block.get("lineno", 1)
        complexities.append(cc)

        if cc > max_cc:
            label = _RANK_LABEL.get(rank, rank)
            issues.append({
                "code": "C101",
                "severity": "warning" if cc <= 20 else "error",
                "line": lineno,
                "col": block.get("col_offset", 0) + 1,
                "message": (
                    f'"{name}" has cyclomatic complexity {cc} '
                    f'(rank {rank} — {label}, threshold >{max_cc}).'
                ),
                "suggestion": (
                    f"Break this function into smaller pieces. Aim for CC ≤ {max_cc} (rank A/B)."
                ),
                "category": "complexity",
            })

    avg_cc = round(sum(complexities) / len(complexities), 1) if complexities else 0
    max_found = max(complexities) if complexities else 0

    return {
        "issues": issues,
        "metrics": {
            "Functions": len(complexities),
            "Avg complexity": avg_cc,
            "Max complexity": max_found,
        },
    }


def _fallback(tree: ast.AST, settings: dict) -> dict:
    max_cc = settings.get("maxComplexity", 10)
    issues: list[dict] = []
    complexities: list[int] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = _compute_cc(node)
            complexities.append(cc)
            if cc > max_cc:
                issues.append({
                    "code": "C101",
                    "severity": "warning",
                    "line": node.lineno,
                    "col": 1,
                    "message": f'Function "{node.name}" has cyclomatic complexity {cc} (>{max_cc}).',
                    "suggestion": "Break this function into smaller pieces. Aim for complexity ≤ 10.",
                    "category": "complexity",
                })

    avg_cc = round(sum(complexities) / len(complexities), 1) if complexities else 0

    return {
        "issues": issues,
        "metrics": {
            "Functions": len(complexities),
            "Avg complexity": avg_cc,
            "Max complexity": max(complexities) if complexities else 0,
        },
    }


def _compute_cc(func_node) -> int:
    count = 1
    for node in ast.walk(func_node):
        if node is func_node:
            continue
        if isinstance(node, _BRANCH_NODES):
            count += 1
        elif isinstance(node, ast.BoolOp):
            count += len(node.values) - 1
    return count
