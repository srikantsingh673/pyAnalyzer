from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ruff_runner

_WATCHED_LIBS = {"pandas", "numpy", "requests", "os"}

_SEVERITY_PD: dict[str, str] = {
    "PD002": "info",
    "PD003": "info",
    "PD004": "info",
    "PD007": "warning",
    "PD008": "info",
    "PD009": "info",
    "PD010": "info",
    "PD011": "info",
    "PD015": "info",
    "PD901": "info",
}

_SUGGESTIONS_PD: dict[str, str] = {
    "PD002": "Use `df = df.operation(...)` instead of `df.operation(inplace=True)`.",
    "PD003": "Use `.isna()` — `.isnull()` is an alias but `.isna()` is preferred.",
    "PD004": "Use `.notna()` — `.notnull()` is an alias but `.notna()` is preferred.",
    "PD007": "`.ix` is removed in pandas 1.0+. Use `.loc` (label) or `.iloc` (position).",
    "PD008": "Use `.loc[row_label, col_label]` for label-based indexing.",
    "PD009": "Use `.iat[row, col]` for fast scalar access by integer position.",
    "PD010": "Prefer `.pivot_table()` — it handles duplicate values and aggregation.",
    "PD011": "Use `.to_numpy()` instead of `.values` to get an ndarray.",
    "PD015": "Use `pd.merge(left, right, ...)` instead of `left.merge(right, ...)`.",
    "PD901": "Choose a descriptive variable name instead of `df`.",
}


def run(tree: ast.AST, source: str, settings: dict, file_path: str = "") -> list[dict]:
    issues: list[dict] = []
    imported = _detect_imports(tree)

    if "pandas" in imported:
        if file_path and ruff_runner.is_available():
            issues += _pandas_from_ruff(file_path, settings)
        else:
            issues += _check_pandas_ast(tree, imported["pandas"])

    if "numpy" in imported:
        issues += _check_numpy(tree, imported["numpy"])
    if "requests" in imported:
        issues += _check_requests(tree, imported["requests"])
    if "os" in imported:
        issues += _check_os(tree)

    return issues


def _detect_imports(tree: ast.AST) -> dict[str, str]:
    result: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _WATCHED_LIBS:
                    result[root] = alias.asname or root

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in _WATCHED_LIBS:
                    result.setdefault(root, root)

    return result


def _pandas_from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_pd(i) for i in ruff_runner.filter_codes(raw, "PD")]


def _map_pd(i: dict) -> dict:
    code = i.get("code") or "PD000"
    return {
        "code": code,
        "severity": _SEVERITY_PD.get(code, "info"),
        "line": i["location"]["row"],
        "col": i["location"]["column"] + 1,
        "message": i["message"],
        "suggestion": _SUGGESTIONS_PD.get(code, "Follow pandas best practices."),
        "category": "library:pandas",
    }


def _check_pandas_ast(tree: ast.AST, alias: str) -> list[dict]:
    issues: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _is_method_call(node, "iterrows"):
                issues.append(_issue("L101", "warning", node.lineno, node.col_offset + 1,
                    "`.iterrows()` is very slow on large DataFrames.",
                    "Use `.itertuples()`, vectorised operations, or `.apply()` instead.",
                    "library:pandas"))

            if (isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Subscript)
                    and isinstance(node.func.value.value, ast.Subscript)):
                issues.append(_issue("L102", "warning", node.lineno, node.col_offset + 1,
                    "Possible chained indexing on a DataFrame.",
                    "Use `.loc[row, col]` or `.iloc[row, col]` to avoid SettingWithCopyWarning.",
                    "library:pandas"))

        if isinstance(node, ast.keyword):
            if (node.arg == "inplace"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is True):
                issues.append(_issue("PD002", "info", node.value.lineno, 1,
                    "`inplace=True` can cause subtle bugs and is not always faster.",
                    _SUGGESTIONS_PD["PD002"], "library:pandas"))

    return issues


def _check_numpy(tree: ast.AST, alias: str) -> list[dict]:
    issues: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            if isinstance(node.iter, (ast.Subscript, ast.Call)):
                issues.append(_issue("L201", "info", node.lineno, node.col_offset + 1,
                    "Possible Python loop over a NumPy array.",
                    "Use vectorised NumPy operations instead of Python for-loops.",
                    "library:numpy"))

        if isinstance(node, ast.Call):
            if (_is_attr_call(node, alias, "sum")
                    and node.args
                    and isinstance(node.args[0], (ast.List, ast.ListComp))):
                issues.append(_issue("L202", "info", node.lineno, node.col_offset + 1,
                    f"`{alias}.sum()` called on a Python list — convert to array first.",
                    f"Use `{alias}.array([...])` to create an ndarray before summing.",
                    "library:numpy"))

    return issues


def _check_requests(tree: ast.AST, alias: str) -> list[dict]:
    issues: list[dict] = []
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options", "request"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_attr_call(node, alias, *http_methods):
            kwarg_names = {kw.arg for kw in node.keywords}

            if "timeout" not in kwarg_names:
                issues.append(_issue("L301", "warning", node.lineno, node.col_offset + 1,
                    "HTTP request made without a `timeout` argument.",
                    "Add `timeout=10` (seconds) to prevent the request hanging indefinitely.",
                    "library:requests"))

            for kw in node.keywords:
                if (kw.arg == "verify"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is False):
                    issues.append(_issue("L302", "error", node.lineno, node.col_offset + 1,
                        "`verify=False` disables SSL certificate verification.",
                        "Remove `verify=False` or supply a proper CA bundle path.",
                        "library:requests"))

    return issues


def _check_os(tree: ast.AST) -> list[dict]:
    issues: list[dict] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_attr_call(node, "os", "system"):
            issues.append(_issue("L401", "warning", node.lineno, node.col_offset + 1,
                "`os.system()` is less safe and flexible than `subprocess`.",
                "Use `subprocess.run([...], check=True)` instead.",
                "library:os"))

    return issues


def _is_method_call(node: ast.Call, *method_names: str) -> bool:
    return isinstance(node.func, ast.Attribute) and node.func.attr in method_names


def _is_attr_call(node: ast.Call, obj_name: str, *attr_names: str) -> bool:
    return (isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == obj_name
            and node.func.attr in attr_names)


def _issue(code, severity, line, col, message, suggestion, category) -> dict:
    return dict(code=code, severity=severity, line=line, col=col,
                message=message, suggestion=suggestion, category=category)
