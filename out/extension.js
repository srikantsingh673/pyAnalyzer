"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const path = __importStar(require("path"));
function activate(context) {
    const diagnostics = vscode.languages.createDiagnosticCollection("analyzr");
    context.subscriptions.push(diagnostics);
    const command = vscode.commands.registerCommand("analyzr.evaluate", async () => {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage("Analyzr: No file is open.");
            return;
        }
        if (editor.document.languageId !== "python") {
            vscode.window.showErrorMessage("Analyzr: This command only works on Python files.");
            return;
        }
        await editor.document.save();
        const filePath = editor.document.uri.fsPath;
        const cfg = vscode.workspace.getConfiguration("analyzr");
        const payload = JSON.stringify({
            file: filePath,
            settings: {
                maxLineLength: cfg.get("maxLineLength", 88),
                maxComplexity: cfg.get("maxComplexity", 10),
                checks: {
                    whitespace: cfg.get("checks.whitespace", true),
                    lineTooLong: cfg.get("checks.lineTooLong", true),
                    docstrings: cfg.get("checks.docstrings", true),
                    complexity: cfg.get("checks.complexity", true),
                    imports: cfg.get("checks.imports", true),
                    typeAnnotations: cfg.get("checks.typeAnnotations", true),
                    libraryRules: cfg.get("checks.libraryRules", true),
                    security: cfg.get("checks.security", false),
                }
            }
        });
        const serverPath = path.join(context.extensionPath, "bundled", "server.py");
        const python = process.platform === "win32" ? "python" : "python3";
        vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "Analyzr: Analysing…", cancellable: false }, () => new Promise((resolve) => {
            let stdout = "";
            let stderr = "";
            const proc = cp.spawn(python, [serverPath]);
            proc.stdout.on("data", (d) => { stdout += d.toString(); });
            proc.stderr.on("data", (d) => { stderr += d.toString(); });
            proc.on("close", (code) => {
                resolve();
                if (code !== 0 || !stdout.trim()) {
                    vscode.window.showErrorMessage(`Analyzr error:\n${stderr || "No output from server.py"}`);
                    return;
                }
                try {
                    const report = JSON.parse(stdout);
                    populateDiagnostics(diagnostics, editor.document.uri, report);
                    showReportPanel(context, report, filePath, diagnostics, editor.document.uri);
                }
                catch {
                    vscode.window.showErrorMessage(`Analyzr: Could not parse report.\n${stdout}`);
                }
            });
            proc.stdin.write(payload + "\n");
            proc.stdin.end();
        }));
    });
    context.subscriptions.push(command);
    context.subscriptions.push(vscode.workspace.onDidCloseTextDocument((doc) => {
        diagnostics.delete(doc.uri);
    }));
}
function populateDiagnostics(collection, uri, report) {
    const diags = [];
    for (const issue of report.issues ?? []) {
        const line = Math.max(0, (issue.line ?? 1) - 1);
        const col = Math.max(0, (issue.col ?? 1) - 1);
        const range = new vscode.Range(line, col, line, col + (issue.length ?? 80));
        const severity = issue.severity === "error" ? vscode.DiagnosticSeverity.Error :
            issue.severity === "warning" ? vscode.DiagnosticSeverity.Warning :
                vscode.DiagnosticSeverity.Information;
        const d = new vscode.Diagnostic(range, `[${issue.code}] ${issue.message}`, severity);
        d.source = "Analyzr";
        diags.push(d);
    }
    collection.set(uri, diags);
}
function showReportPanel(_context, report, filePath, diagnostics, uri) {
    const panel = vscode.window.createWebviewPanel("analyzrReport", `Evaluation: ${path.basename(filePath)}`, vscode.ViewColumn.Beside, { enableScripts: true });
    panel.webview.html = buildHtml(report, filePath);
    panel.onDidDispose(() => diagnostics.delete(uri));
}
function buildHtml(report, filePath) {
    const score = report.summary?.score ?? 0;
    const scoreColor = score >= 80 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
    const issueRows = (report.issues ?? []).map((i) => `
    <tr class="sev-${i.severity}">
      <td>${i.severity.toUpperCase()}</td>
      <td>${i.code}</td>
      <td>Line ${i.line ?? "?"}, Col ${i.col ?? "?"}</td>
      <td>${escHtml(i.message)}</td>
      <td>${escHtml(i.suggestion ?? "")}</td>
    </tr>`).join("");
    const metricCards = Object.entries(report.metrics ?? {}).map(([k, v]) => `
    <div class="card"><div class="card-val">${v}</div><div class="card-lbl">${k}</div></div>`).join("");
    return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family); color: var(--vscode-foreground);
         background: var(--vscode-editor-background); padding: 16px; font-size: 13px; }
  h1   { font-size: 16px; font-weight: 500; margin: 0 0 4px; }
  .path { color: var(--vscode-descriptionForeground); font-size: 11px; margin-bottom: 16px; }
  .score-ring { display:inline-block; font-size:42px; font-weight:600;
                color:${scoreColor}; margin-bottom:16px; }
  .score-label { font-size:12px; color:var(--vscode-descriptionForeground); }
  .metrics { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:20px; }
  .card { background:var(--vscode-editorWidget-background); border:1px solid var(--vscode-widget-border,#444);
          border-radius:6px; padding:10px 16px; min-width:90px; text-align:center; }
  .card-val { font-size:22px; font-weight:500; }
  .card-lbl { font-size:11px; color:var(--vscode-descriptionForeground); margin-top:2px; }
  table { width:100%; border-collapse:collapse; font-size:12px; }
  th    { text-align:left; padding:6px 8px; border-bottom:1px solid var(--vscode-widget-border,#444);
          color:var(--vscode-descriptionForeground); font-weight:500; }
  td    { padding:5px 8px; border-bottom:1px solid var(--vscode-widget-border,#333); vertical-align:top; }
  .sev-error   td:first-child { color:#ef4444; font-weight:500; }
  .sev-warning td:first-child { color:#f59e0b; font-weight:500; }
  .sev-info    td:first-child { color:#60a5fa; }
  h2 { font-size:13px; font-weight:500; margin:20px 0 8px; border-bottom:1px solid var(--vscode-widget-border,#444); padding-bottom:4px; }
</style>
</head>
<body>
  <h1>Analyzr Report</h1>
  <div class="path">${escHtml(filePath)}</div>

  <div class="score-ring">${score}<span style="font-size:20px">/100</span></div>
  <div class="score-label">Overall score</div>

  <h2>Metrics</h2>
  <div class="metrics">${metricCards}</div>

  <h2>Issues (${(report.issues ?? []).length})</h2>
  <table>
    <thead><tr><th>Severity</th><th>Code</th><th>Location</th><th>Message</th><th>Suggestion</th></tr></thead>
    <tbody>${issueRows || '<tr><td colspan="5" style="color:#22c55e">No issues found</td></tr>'}</tbody>
  </table>
</body>
</html>`;
}
function escHtml(s) {
    return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function deactivate() { }
