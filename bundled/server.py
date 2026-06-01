import sys
import json
import ast
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from checkers.ast_checker import run as ast_check
from checkers.style_checker import run as style_check
from checkers.doc_checker import run as doc_check
from checkers.import_checker import run as import_check
from checkers.library_checker import run as library_check
from checkers.complexity_checker import run as complexity_check
from report_builder import build_report


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        _fatal("No input received on stdin.")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        _fatal(f"Invalid JSON from extension: {e}")

    file_path = payload.get("file", "")
    settings = payload.get("settings", {})
    checks = settings.get("checks", {})

    if not file_path or not Path(file_path).exists():
        _fatal(f"File not found: {file_path}")

    source = Path(file_path).read_text(encoding="utf-8", errors="replace")

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as e:
        # still emit a partial report with the syntax error as the only issue
        tree = None
        syntax_issue = {
            "code": "E001",
            "severity": "error",
            "line": e.lineno or 1,
            "col": e.offset or 1,
            "message": f"SyntaxError: {e.msg}",
            "suggestion": "Fix the syntax error before running further checks.",
            "category": "syntax",
        }

    issues = []
    metrics = {}
    start = time.perf_counter()

    if tree is None:
        issues.append(syntax_issue)
    else:
        if checks.get("imports", True):
            issues += import_check(tree, source, settings, file_path=file_path)

        if checks.get("whitespace", True) or checks.get("lineTooLong", True):
            issues += style_check(source, settings, file_path=file_path)

        if checks.get("docstrings", True):
            issues += doc_check(tree, source, settings, file_path=file_path)

        if checks.get("complexity", True):
            result = complexity_check(tree, settings, file_path=file_path)
            issues += result["issues"]
            metrics.update(result["metrics"])

        if checks.get("typeAnnotations", True):
            issues += ast_check(tree, source, settings, file_path=file_path)

        if checks.get("libraryRules", True):
            issues += library_check(tree, source, settings, file_path=file_path)

    elapsed = round(time.perf_counter() - start, 3)
    report = build_report(issues, metrics, source, file_path, elapsed, settings)

    sys.stdout.write(json.dumps(report))
    sys.stdout.flush()


def _fatal(msg: str):
    sys.stdout.write(json.dumps({
        "summary": {"score": 0},
        "issues": [{"code": "E000", "severity": "error", "line": 1, "col": 1,
                    "message": msg, "suggestion": "", "category": "internal"}],
        "metrics": {},
    }))
    sys.exit(1)


if __name__ == "__main__":
    main()
