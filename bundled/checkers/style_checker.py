from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools import ruff_runner

_STYLE_PREFIXES = ("E1", "E2", "E3", "E501", "W1", "W2", "W3", "W5", "W6")

_SUGGESTIONS: dict[str, str] = {
    "E101": "Use consistent spaces (PEP8 recommends 4 spaces per indent level).",
    "E111": "Use 4 spaces per indentation level.",
    "E114": "Continuation line indentation is not aligned with opening delimiter.",
    "E117": "Remove the extra indentation on this line.",
    "E121": "Fix continuation line indentation.",
    "E125": "Continuation line indentation does not match visual indentation.",
    "E131": "Continuation line unaligned for block comment.",
    "E201": "Remove the whitespace after the opening bracket.",
    "E202": "Remove the whitespace before the closing bracket.",
    "E203": "Remove the whitespace before ':'.",
    "E211": "Remove whitespace before '(' or '['.",
    "E225": "Add spaces around the operator.",
    "E228": "Add spaces around the modulo operator.",
    "E231": "Add a space after ',' / ':' / ';'.",
    "E251": "Remove spaces around keyword / parameter default '='.",
    "E261": "Use at least two spaces before an inline comment.",
    "E262": "Inline comment should start with '# '.",
    "E265": "Block comment should start with '# '.",
    "E266": "Block comment should start with '## '.",
    "E271": "Use a single space after the keyword.",
    "E272": "Use a single space before the keyword.",
    "E301": "Add a blank line before this function or class definition.",
    "E302": "Add 2 blank lines before this top-level function or class definition.",
    "E303": "Reduce to at most 2 consecutive blank lines.",
    "E304": "Remove the blank line(s) after @decorator.",
    "E305": "Add 2 blank lines after the last top-level function/class definition.",
    "E401": "Put each import on a separate line.",
    "E501": "Shorten this line or split it using parentheses or a backslash.",
    "W191": "Use spaces for indentation, not tabs (PEP8).",
    "W291": "Remove trailing whitespace.",
    "W293": "Remove the whitespace before ':'.",
    "W391": "Remove the trailing blank line at the end of the file.",
    "W503": "Put the line break after the binary operator, not before.",
    "W504": "Put the line break before the binary operator, not after.",
}


def run(source: str, settings: dict, file_path: str = "") -> list[dict]:
    if file_path and ruff_runner.is_available():
        return _from_ruff(file_path, settings)
    return _fallback(source, settings)



def _from_ruff(file_path: str, settings: dict) -> list[dict]:
    raw = ruff_runner.get(file_path, settings)
    return [_map_ruff(i) for i in ruff_runner.filter_codes(raw, *_STYLE_PREFIXES)]


def _map_ruff(i: dict) -> dict:
    code = i.get("code") or "E000"
    sev  = "info" if code.startswith("W") else "warning"
    return {
        "code":       code,
        "severity":   sev,
        "line":       i["location"]["row"],
        "col":        i["location"]["column"] + 1,
        "message":    i["message"],
        "suggestion": _SUGGESTIONS.get(code, "See PEP8 style guide (https://peps.python.org/pep-0008/)."),
        "category":   "style",
    }



def _fallback(source: str, settings: dict) -> list[dict]:
    checks  = settings.get("checks", {})
    max_len = settings.get("maxLineLength", 88)
    issues  = []
    lines   = source.splitlines(keepends=True)
    blank_streak = 0

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\n\r")

        if checks.get("lineTooLong", True) and len(line) > max_len:
            issues.append(_issue("E501", "warning", lineno, max_len + 1,
                f"Line too long ({len(line)} > {max_len} characters).",
                f"Shorten to {max_len} characters or fewer.", "style"))

        if checks.get("whitespace", True):
            stripped = line.rstrip()
            if stripped != line:
                issues.append(_issue("W291", "info", lineno, len(stripped) + 1,
                    f"Trailing whitespace ({len(line) - len(stripped)} space(s)).",
                    "Remove whitespace at end of line.", "style"))

            if line.strip() == "":
                blank_streak += 1
            else:
                if blank_streak > 2:
                    issues.append(_issue("E303", "info", lineno - 1, 1,
                        f"{blank_streak} consecutive blank lines (PEP8 allows max 2).",
                        "Reduce to at most 2 consecutive blank lines.", "style"))
                blank_streak = 0

            indent = line[: len(line) - len(line.lstrip())]
            if "\t" in indent and " " in indent:
                issues.append(_issue("E101", "warning", lineno, 1,
                    "Mixed tabs and spaces in indentation.",
                    "Use spaces only (4 spaces per indent level).", "style"))

    if checks.get("whitespace", True) and source and not source.endswith("\n"):
        issues.append(_issue("W391", "info", len(lines), 1,
            "No newline at end of file.",
            "Add a newline character at the end of the file.", "style"))

    return issues


def _issue(code, severity, line, col, message, suggestion, category) -> dict:
    return dict(code=code, severity=severity, line=line, col=col,
                message=message, suggestion=suggestion, category=category)
