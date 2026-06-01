from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ruff_runner, mypy_runner

_BUG_PREFIXES = ("B", "E711", "E712", "E721", "E722")
_ANN_PREFIXES = ("ANN",)

_SEVERITY: dict[str, str] = {
    "B006": "warning", "B007": "info",  "B008": "warning",
    "B011": "warning", "B015": "info",  "B018": "info",
    "B021": "warning", "B023": "warning", "B024": "warning",
    "E711": "warning", "E712": "info",  "E721": "warning",
    "E722": "warning",
}

_SUGGESTIONS: dict[str, str] = {
    "B006": "Use `None` as default and create the mutable object inside the function body.",
    "B007": "Prefix the variable with `_` if it is intentionally unused.",
    "B008": "Avoid calling functions in default arguments — the call runs only once at definition time.",
    "B011": "Raise a specific exception instead: `raise AssertionError('reason')`.",
    "B015": "Remove or move this comparison; standalone comparisons have no effect.",
    "B018": "Remove this expression; it has no side-effects.",
    "B021": "Add a `{placeholder}` or use a regular string instead of an f-string.",
    "B023": "Capture the loop variable in a default arg: `lambda x=item: ...`.",
    "B024": "Add `@abstractmethod` to at least one method, or remove ABC.",
    "E711": "Use `is None` / `is not None` instead of `== None` / `!= None`.",
    "E712": "Use `if x:` / `if not x:` instead of `== True` / `== False`.",
    "E721": "Use `isinstance(x, Type)` instead of `type(x) == Type`.",
    "E722": "Catch a specific exception: `except ValueError:` or at minimum `except Exception:`.",
    "ANN001": "Add a type annotation to this argument, e.g. `arg: int`.",
    "ANN002": "Add a type annotation to *args, e.g. `*args: str`.",
    "ANN003": "Add a type annotation to **kwargs, e.g. `**kwargs: Any`.",
    "ANN201": "Add a return type annotation, e.g. `-> int` or `-> None`.",
    "ANN202": "Add a return type annotation to this private function.",
}

_MAX_ARGS = 5


def run(tree: ast.AST, source: str, settings: dict, file_path: str = "") -> list[dict]:
    issues: list[dict] = []

    if file_path and ruff_runner.is_available():
        issues += _bugs_from_ruff(file_path, settings)
        if settings.get("checks", {}).get("typeAnnotations", True):
            issues += _annotations_from_ruff(file_path, settings)
    else:
        issues += _fallback(tree, settings)

    # mypy runs on top of ruff's annotation checks for full type inference
    if (file_path
            and mypy_runner.is_available()
            and settings.get("checks", {}).get("typeAnnotations", True)):
        issues += _from_mypy(file_path)

    return issues


def _bugs_from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_ruff(i, "code-quality") for i in ruff_runner.filter_codes(raw, *_BUG_PREFIXES)]


def _annotations_from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_ruff(i, "type-annotations") for i in ruff_runner.filter_codes(raw, *_ANN_PREFIXES)]


def _map_ruff(i: dict, category: str) -> dict:
    code = i.get("code") or "B000"
    return {
        "code": code,
        "severity": _SEVERITY.get(code, "info"),
        "line": i["location"]["row"],
        "col": i["location"]["column"] + 1,
        "message": i["message"],
        "suggestion": _SUGGESTIONS.get(code, "Review this code pattern."),
        "category": category,
    }


def _from_mypy(file_path: str) -> list[dict]:
    issues = []
    for m in mypy_runner.run(file_path):
        sev = m.get("severity", "error")
        issues.append({
            "code": f"MY{m.get('code', '000')}",
            "severity": "error" if sev == "error" else "warning",
            "line": m.get("line", 1),
            "col": m.get("column", 0) + 1,
            "message": m.get("message", ""),
            "suggestion": "Fix the type error reported by mypy.",
            "category": "type-annotations",
        })
    return issues


def _fallback(tree: ast.AST, settings: dict) -> list[dict]:
    issues: list[dict] = []
    checks = settings.get("checks", {})

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_function(node, issues, checks)
        elif isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.append(_issue("E722", "warning", node.lineno, 1,
                    "Bare `except:` clause catches everything including KeyboardInterrupt.",
                    _SUGGESTIONS["E722"], "code-quality"))
        elif isinstance(node, ast.Compare):
            _check_comparison(node, issues)

    return issues


def _check_function(node, issues: list, checks: dict):
    args = node.args
    all_args = args.args + args.posonlyargs + args.kwonlyargs
    real_args = [a for a in all_args if a.arg not in ("self", "cls")]

    if len(real_args) > _MAX_ARGS:
        issues.append(_issue("A103", "warning", node.lineno, 1,
            f'Function "{node.name}" has {len(real_args)} arguments (>{_MAX_ARGS}).',
            "Group related arguments into a dataclass or config object.", "code-quality"))

    if checks.get("typeAnnotations", True):
        if not node.name.startswith("__") and node.returns is None:
            issues.append(_issue("ANN201", "info", node.lineno, 1,
                f'Function "{node.name}" is missing a return type annotation.',
                _SUGGESTIONS["ANN201"], "type-annotations"))

        for arg in real_args:
            if arg.annotation is None:
                issues.append(_issue("ANN001", "info", node.lineno, 1,
                    f'Argument "{arg.arg}" in "{node.name}" has no type annotation.',
                    _SUGGESTIONS["ANN001"], "type-annotations"))

    for default in args.defaults + args.kw_defaults:
        if default is None:
            continue
        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
            issues.append(_issue("B006", "warning", node.lineno, 1,
                f'Mutable default argument ({type(default).__name__.lower()}) in "{node.name}".',
                _SUGGESTIONS["B006"], "code-quality"))


def _check_comparison(node: ast.Compare, issues: list):
    for op, comparator in zip(node.ops, node.comparators):
        if isinstance(op, (ast.Eq, ast.NotEq)):
            if isinstance(comparator, ast.Constant) and comparator.value is None:
                op_str = "==" if isinstance(op, ast.Eq) else "!="
                issues.append(_issue("E711", "warning", node.lineno, node.col_offset + 1,
                    f"Use `is None` / `is not None` instead of `{op_str} None`.",
                    _SUGGESTIONS["E711"], "code-quality"))

        if isinstance(op, ast.Eq):
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, bool):
                issues.append(_issue("E712", "info", node.lineno, node.col_offset + 1,
                    f"Avoid comparing to `{comparator.value}` with `==`.",
                    _SUGGESTIONS["E712"], "code-quality"))


def _issue(code, severity, line, col, message, suggestion, category) -> dict:
    return dict(code=code, severity=severity, line=line, col=col,
                message=message, suggestion=suggestion, category=category)
