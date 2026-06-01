from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ruff_runner

_DOC_PREFIXES = ("D",)

_MISSING = {"D100", "D101", "D102", "D103", "D104", "D105", "D107", "D419"}

_SUGGESTIONS: dict[str, str] = {
    "D100": 'Add a module docstring: """One-line summary of this module."""',
    "D101": 'Add a class docstring: class Foo:\n    """Short description."""',
    "D102": 'Add a method docstring: def method(self):\n    """Short description."""',
    "D103": 'Add a function docstring: def func():\n    """Short description."""',
    "D104": 'Add an __init__.py docstring: """Package description."""',
    "D105": "Add a docstring to this magic method.",
    "D107": 'Add a docstring to __init__: def __init__(self):\n    """Initialise ..."""',
    "D200": "Remove blank lines inside the one-line docstring.",
    "D201": "Remove blank line before the docstring.",
    "D202": "Remove blank line after the docstring.",
    "D205": "Add one blank line between the summary sentence and the description.",
    "D206": "Use spaces for docstring indentation, not tabs.",
    "D207": "Reduce docstring indentation to match the surrounding code.",
    "D208": "Reduce docstring indentation — it is over-indented.",
    "D209": "Put the closing triple-quotes on their own line.",
    "D210": "Remove leading/trailing whitespace around docstring text.",
    "D211": "Remove the blank line before the class docstring.",
    "D213": "Put the summary sentence on the second line (after the opening quotes).",
    "D300": 'Use triple double-quotes: """...""" not \'\'\'...\'\'\'.',
    "D400": "End the docstring summary with a period.",
    "D415": "End the docstring summary with a period, question mark, or exclamation point.",
    "D419": "Docstring is empty — add a description.",
}


def run(tree: ast.AST, _source: str, settings: dict, file_path: str = "") -> list[dict]:
    if file_path and ruff_runner.is_available():
        return _from_ruff(file_path, settings)
    return _fallback(tree)



def _from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_ruff(i) for i in ruff_runner.filter_codes(raw, *_DOC_PREFIXES)]


def _map_ruff(i: dict) -> dict:
    code = i.get("code") or "D000"
    return {
        "code":       code,
        "severity":   "warning" if code in _MISSING else "info",
        "line":       i["location"]["row"],
        "col":        i["location"]["column"] + 1,
        "message":    i["message"],
        "suggestion": _SUGGESTIONS.get(code, "Follow PEP257 docstring conventions."),
        "category":   "docstring",
    }



def _fallback(tree: ast.AST) -> list[dict]:
    issues: list[dict] = []

    # Module docstring
    if not (tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)
            and isinstance(tree.body[0].value.value, str)):
        issues.append(_issue("D100", "info", 1, 1,
            "Missing module-level docstring.",
            _SUGGESTIONS["D100"], "docstring"))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _check_callable(node, issues)
        elif isinstance(node, ast.ClassDef):
            _check_class(node, issues)

    return issues


def _get_docstring_node(node):
    if (node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)):
        return node.body[0].value
    return None


def _check_callable(node, issues: list):
    if node.name.startswith("__") and node.name.endswith("__"):
        if node.name not in ("__init__", "__call__", "__str__", "__repr__"):
            return
    doc_node = _get_docstring_node(node)
    if doc_node is None:
        code = "D107" if node.name == "__init__" else "D103"
        issues.append(_issue(code, "warning", node.lineno, 1,
            f'Function "{node.name}" is missing a docstring.',
            _SUGGESTIONS.get(code, "Add a docstring."), "docstring"))
        return
    _check_quality(doc_node.value, doc_node.lineno, node.name, issues)


def _check_class(node, issues: list):
    doc_node = _get_docstring_node(node)
    if doc_node is None:
        issues.append(_issue("D101", "warning", node.lineno, 1,
            f'Class "{node.name}" is missing a docstring.',
            _SUGGESTIONS["D101"], "docstring"))
        return
    _check_quality(doc_node.value, doc_node.lineno, node.name, issues)


def _check_quality(text: str, lineno: int, name: str, issues: list):
    stripped = text.strip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if first_line and not first_line.endswith((".", "!", "?")):
        issues.append(_issue("D415", "info", lineno, 1,
            f'Docstring for "{name}" summary line does not end with punctuation.',
            _SUGGESTIONS["D415"], "docstring"))
    lines = text.splitlines()
    if len(lines) > 1 and lines[-1].strip() == "":
        issues.append(_issue("D209", "info", lineno, 1,
            f'Docstring for "{name}" has a trailing blank line before closing quotes.',
            _SUGGESTIONS["D209"], "docstring"))


def _issue(code, severity, line, col, message, suggestion, category) -> dict:
    return dict(code=code, severity=severity, line=line, col=col,
                message=message, suggestion=suggestion, category=category)
