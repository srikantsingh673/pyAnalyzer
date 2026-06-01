from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ruff_runner

_IMPORT_PREFIXES = ("F4", "F8", "E401", "E402", "I")

_SEVERITY: dict[str, str] = {
    "F401": "warning",
    "F403": "warning",
    "F405": "warning",
    "F811": "warning",
    "E401": "info",
    "E402": "info",
    "I001": "info",
}

_SUGGESTIONS: dict[str, str] = {
    "F401": "Remove the import or prefix it with `_` to mark it as intentionally unused.",
    "F403": "Replace `import *` with explicit names: `from module import Name1, Name2`.",
    "F405": "Avoid star imports — the name's origin is ambiguous.",
    "F811": "Remove the duplicate import; the earlier one will be silently overwritten.",
    "E401": "Put each import on its own line.",
    "E402": "Move all imports to the top of the file (after the module docstring).",
    "I001": "Sort and group imports with isort: stdlib → third-party → local.",
}


def run(tree: ast.AST, source: str, settings: dict, file_path: str = "") -> list[dict]:
    if file_path and ruff_runner.is_available():
        return _from_ruff(file_path, settings)
    return _fallback(tree, source)


def _from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_ruff(i) for i in ruff_runner.filter_codes(raw, *_IMPORT_PREFIXES)]


def _map_ruff(i: dict) -> dict:
    code = i.get("code") or "F000"
    return {
        "code":       code,
        "severity":   _SEVERITY.get(code, "warning"),
        "line":       i["location"]["row"],
        "col":        i["location"]["column"] + 1,
        "message":    i["message"],
        "suggestion": _SUGGESTIONS.get(code, "Review import statement."),
        "category":   "imports",
    }


# ---------------------------------------------------------------------------
# Fallback AST-based analysis (used when ruff is unavailable)
# ---------------------------------------------------------------------------

def _fallback(tree: ast.AST, source: str) -> list[dict]:
    imported_names, issues = _collect_import_issues(tree)
    used_names = _collect_used_names(tree)
    issues += _find_unused_imports(imported_names, used_names)
    issues += _find_late_imports(tree)
    return issues


def _collect_import_issues(tree: ast.AST) -> tuple[list[tuple[str, int]], list[dict]]:
    """Walk the tree and flag wildcard imports and duplicate imports."""
    issues: list[dict] = []
    imported_names: list[tuple[str, int]] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            _check_import_from(node, imported_names, seen, issues)
        elif isinstance(node, ast.Import):
            _check_import(node, imported_names, seen, issues)

    return imported_names, issues


def _check_import_from(
    node: ast.ImportFrom,
    imported_names: list[tuple[str, int]],
    seen: set[str],
    issues: list[dict],
) -> None:
    """Process a single `from X import ...` statement."""
    for alias in node.names:
        if alias.name == "*":
            mod = node.module or "?"
            issues.append(_issue(
                "F403", "warning", node.lineno, 1,
                f"Wildcard import: `from {mod} import *`.",
                f"Import only what you need: `from {mod} import SpecificName`.",
                "imports",
            ))
        else:
            bound = alias.asname or alias.name
            imported_names.append((bound, node.lineno))
            key = f"from:{node.module}:{alias.name}"
            if key in seen:
                issues.append(_issue(
                    "F811", "warning", node.lineno, 1,
                    f"Duplicate import: `{alias.name}` already imported.",
                    "Remove the duplicate import statement.",
                    "imports",
                ))
            seen.add(key)


def _check_import(
    node: ast.Import,
    imported_names: list[tuple[str, int]],
    seen: set[str],
    issues: list[dict],
) -> None:
    """Process a single `import X` statement."""
    for alias in node.names:
        bound = alias.asname or alias.name.split(".")[0]
        imported_names.append((bound, node.lineno))
        key = f"import:{alias.name}"
        if key in seen:
            issues.append(_issue(
                "F811", "info", node.lineno, 1,
                f"Duplicate import: `{alias.name}` already imported.",
                "Remove the duplicate import statement.",
                "imports",
            ))
        seen.add(key)


def _collect_used_names(tree: ast.AST) -> set[str]:
    """Return every name referenced in the tree (bare names and attribute roots)."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            used.add(node.value.id)
    return used


def _find_unused_imports(
    imported_names: list[tuple[str, int]],
    used_names: set[str],
) -> list[dict]:
    """Flag imported names that never appear in the rest of the file."""
    return [
        _issue(
            "F401", "warning", lineno, 1,
            f"Imported name `{name}` appears unused.",
            "Remove it, or prefix with `_` to suppress this warning.",
            "imports",
        )
        for name, lineno in imported_names
        if name not in used_names and not name.startswith("_")
    ]


def _find_late_imports(tree: ast.AST) -> list[dict]:
    """Flag import statements that appear after executable non-import code (E402)."""
    import_lines = {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
    }
    non_import_lines = {
        node.lineno
        for node in ast.iter_child_nodes(tree)
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.Expr, ast.If, ast.Try))
        and hasattr(node, "lineno")
    }
    return [
        _issue(
            "E402", "info", lineno, 1,
            "Import statement appears after non-import code.",
            "Move all imports to the top of the file.",
            "imports",
        )
        for lineno in import_lines
        if any(earlier < lineno for earlier in non_import_lines)
    ]


def _issue(code, severity, line, col, message, suggestion, category) -> dict:
    return dict(code=code, severity=severity, line=line, col=col,
                message=message, suggestion=suggestion, category=category)
