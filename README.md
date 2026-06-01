# PyAnalyzr

A VS Code extension for evaluating Python code quality. Open any `.py` file, run the command, and get a scored report with inline diagnostics and a full breakdown of every issue.

---

## What it checks

- **Style** — line length, indentation, trailing whitespace, blank lines (ruff E/W)
- **Imports** — unused, wildcard, duplicate, and out-of-order imports (ruff F + isort)
- **Docstrings** — missing or malformed docstrings on modules, classes, and functions (ruff D)
- **Code quality** — mutable default arguments, bare `except`, `== None`, type comparisons (ruff B + E7xx)
- **Type annotations** — missing annotations (ruff ANN) + actual type errors via full type inference (mypy)
- **Complexity** — cyclomatic complexity per function with A–F grades (radon)
- **Library rules** — pandas anti-patterns (ruff PD), NumPy loop usage, requests without timeout, `verify=False`, `os.system()` (custom AST)

Each issue shows a severity (error / warning / info), the rule code, location, and a suggested fix. The overall score starts at 100 and deducts 10 per error, 4 per warning, 1 per info.

---

## Requirements

- VS Code 1.85+
- Python 3.8+ on PATH
- `ruff`, `radon`, and `mypy` installed

Install the Python dependencies before using the extension:

```bash
pip install ruff radon mypy
```

If these are not on PATH, the extension falls back to a built-in AST analyser. It covers the same categories but with reduced accuracy — ruff and mypy do significantly deeper analysis, so installing them is recommended.

---

## Installation

### From VSIX

```bash
code --install-extension analyzr-0.1.0.vsix
```

### From source

```bash
git clone https://github.com/srikant-siddhiyoga/analyzr
cd analyzr
npm install
npm run compile
```

Then open the `analyzr/` folder in VS Code and press **F5** to launch the Extension Development Host.

---

## Usage

Open any Python file, then either:

- Right-click in the editor → **Analyzr: Evaluate This File**
- Command Palette (`Ctrl+Shift+P`) → `Analyzr: Evaluate This File`

A report panel opens beside the editor. Issues also appear in the Problems panel with squiggles.

To test the analysis pipeline without VS Code:

```bash
echo '{"file": "/path/to/file.py", "settings": {}}' | python3 bundled/server.py | python3 -m json.tool
```

---

## Configuration

Settings are in VS Code Settings under **Analyzr**.

| Setting | Default | Description |
|---|---|---|
| `analyzr.maxLineLength` | `88` | Max line length (Black default; PEP 8 is 79) |
| `analyzr.maxComplexity` | `10` | Cyclomatic complexity limit per function |
| `analyzr.checks.whitespace` | `true` | Trailing whitespace and blank line rules |
| `analyzr.checks.lineTooLong` | `true` | Lines over `maxLineLength` |
| `analyzr.checks.docstrings` | `true` | Missing or malformed docstrings |
| `analyzr.checks.complexity` | `true` | Cyclomatic complexity |
| `analyzr.checks.imports` | `true` | Import issues and ordering |
| `analyzr.checks.typeAnnotations` | `true` | Missing annotations and type errors |
| `analyzr.checks.libraryRules` | `true` | Pandas, NumPy, requests, os patterns |
| `analyzr.checks.security` | `false` | Security checks (requires `bandit`) |

---

## How the analysis works

### ruff

ruff is invoked once per file and the result is cached. Each checker filters its own rule prefixes from that single run:

```
E, W   → style_checker      (pycodestyle rules)
F, I   → import_checker     (pyflakes + isort)
D      → doc_checker        (pydocstyle)
B, E7  → ast_checker        (bugbear + comparison rules)
ANN    → ast_checker        (annotation presence)
PD     → library_checker    (pandas-vet)
```

### mypy

mypy runs as a second pass on top of ruff's annotation checks. ruff only verifies that annotations are present; mypy does full type inference and catches things like wrong return types, argument mismatches, and `None` being passed where a value is expected.

### radon

radon measures cyclomatic complexity per function and assigns a grade:

| Grade | CC | Risk |
|---|---|---|
| A | 1–5 | Low |
| B | 6–10 | Manageable |
| C | 11–15 | Medium — flagged |
| D | 16–20 | High — flagged |
| E | 21–25 | Very high — flagged |
| F | 26+ | Untestable — flagged |

### AST fallback

When ruff, radon, or mypy are not installed, the relevant checker falls back to a custom AST walk that covers the same rules without any external dependencies. The fallback is less accurate (no name-binding analysis, no type inference) but produces usable output.

---

## Project structure

```
analyzr/
├── src/extension.ts           — VS Code extension entry point
├── bundled/
│   ├── server.py              — Reads stdin JSON, runs checkers, writes report JSON
│   ├── report_builder.py      — Assembles final report and computes score
│   ├── checkers/
│   │   ├── style_checker.py
│   │   ├── doc_checker.py
│   │   ├── import_checker.py
│   │   ├── ast_checker.py
│   │   ├── complexity_checker.py
│   │   └── library_checker.py
│   └── tools/
│       ├── ruff_runner.py     — Single ruff invocation with result cache
│       ├── radon_runner.py    — radon cc wrapper
│       └── mypy_runner.py     — mypy wrapper
└── package.json
```

---

## Extending

### New checker

Create `bundled/checkers/my_checker.py` with a `run(tree, source, settings, file_path) -> list[dict]` function. Each issue needs: `code`, `severity` (`error`/`warning`/`info`), `line`, `col`, `message`, `suggestion`, `category`. Then import and call it in `bundled/server.py`.

### New library rule

Add the library name to `_known` in `_detect_imports()` in `library_checker.py`, write a `_check_yourlibrary(tree, alias)` function, and call it in `run()`.

---

## License

MIT

---

Built by [Srikant](https://github.com/srikant-siddhiyoga)
