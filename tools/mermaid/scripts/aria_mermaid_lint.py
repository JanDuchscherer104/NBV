#!/usr/bin/env python3
"""ARIA-NBV Mermaid linter.

This is intentionally conservative. It catches the failure modes that usually
make Codex-generated Mermaid figures inconsistent with the ARIA-NBV thesis style.
It does not replace rendering with `mmdc`; it complements it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

RESERVED_IDS = {
    "end",
    "default",
    "style",
    "linkStyle",
    "classDef",
    "class",
    "call",
    "href",
    "click",
    "interpolate",
}

REQUIRED_CLASSDEFS = {
    "input": "fill:#D5E8D4,stroke:#82B366,color:#17202A,stroke-width:1.5px,rx:0,ry:0",
    "output": "fill:#F8CECC,stroke:#B85450,color:#17202A,stroke-width:1.5px,rx:0,ry:0",
    "compute": "fill:#E1D5E7,stroke:#9673A6,color:#17202A,stroke-width:1.5px,rx:8,ry:8",
    "data": "fill:#F5F5F5,stroke:#9E9E9E,color:#17202A,stroke-width:1.2px,rx:0,ry:0",
}

NON_CANONICAL_SYMBOLS = {
    r"\\mathbf{e}_{\\mathrm{pose}}": r"\\mathbf{E}_{q}",
    r"\\mathbf{z}_{\\mathrm{traj}}": r"\\mathbf{c}_{\\mathrm{traj}}",
    r"\\mathbf{P}_{\\mathrm{sem}}": r"\\boldsymbol{\\mathcal{P}}^{\\mathrm{semi}}",
    r"\\mathbf{T}^{w}_{r}(t)": r"\\mathbf{T}^{w}_{\\mathrm{rig}}(t)",
}

DIAGRAM_DECL_RE = re.compile(
    r"^\s*(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|gantt|pie|gitGraph|mindmap|timeline|quadrantChart|xychart-beta|block-beta|sankey-beta|packet-beta|architecture-beta)\b",
    re.MULTILINE,
)


def strip_frontmatter(text: str) -> tuple[str | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    # consume closing --- line
    rest_start = text.find("\n", end + 4)
    if rest_start == -1:
        return text[4:end], ""
    return text[4:end], text[rest_start + 1 :]


def line_col(text: str, idx: int) -> tuple[int, int]:
    line = text.count("\n", 0, idx) + 1
    last = text.rfind("\n", 0, idx)
    col = idx + 1 if last == -1 else idx - last
    return line, col


def add_issue(issues: list[tuple[str, str]], severity: str, message: str) -> None:
    issues.append((severity, message))


def lint_text(text: str, path: Path) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []

    if "---" in text and not text.startswith("---\n"):
        add_issue(
            issues, "error", "frontmatter exists but does not start at byte 0 / line 1"
        )

    frontmatter, body = strip_frontmatter(text)
    diagram_match = DIAGRAM_DECL_RE.search(body)
    if not diagram_match:
        add_issue(issues, "warning", "no supported Mermaid diagram declaration found")
        diagram_type = None
    else:
        diagram_type = diagram_match.group(1)
        if diagram_type == "graph":
            add_issue(issues, "warning", "prefer `flowchart` over legacy `graph`")

    has_math = "$$" in text
    if diagram_type in {"flowchart", "graph"}:
        if has_math:
            if not frontmatter:
                add_issue(
                    issues,
                    "error",
                    "math-heavy flowchart should include ARIA-NBV frontmatter",
                )
            else:
                if "htmlLabels: true" not in frontmatter:
                    add_issue(
                        issues,
                        "error",
                        "math-heavy flowchart must set htmlLabels: true",
                    )
                if "layout: elk" not in frontmatter:
                    add_issue(
                        issues,
                        "warning",
                        "math-heavy thesis flowchart should use layout: elk",
                    )
                if "themeCSS:" not in frontmatter:
                    add_issue(
                        issues, "warning", "missing themeCSS font-size normalization"
                    )

        for cls, style in REQUIRED_CLASSDEFS.items():
            pattern = rf"classDef\s+{re.escape(cls)}\s+([^;]+);"
            m = re.search(pattern, body)
            if not m:
                add_issue(issues, "warning", f"missing required classDef `{cls}`")
            elif style not in m.group(1):
                add_issue(
                    issues,
                    "warning",
                    f"classDef `{cls}` differs from ARIA-NBV style guide",
                )

    # Reserved IDs used as node declarations or arrow targets.
    for word in RESERVED_IDS:
        if re.search(rf"^\s*{re.escape(word)}\s*[\[\(\{{]", body, re.MULTILINE):
            add_issue(issues, "error", f"reserved word `{word}` used as node id")
        if re.search(rf"[-.=]+>\s*{re.escape(word)}\b", body):
            add_issue(issues, "error", f"reserved word `{word}` used as arrow target")

    if re.search(r"^\s*%[^%{]", body, re.MULTILINE):
        add_issue(issues, "error", "Mermaid comments must start with `%%`, not `%`")

    if re.search(r"subgraph\s+[^\"\n]*<br", body):
        add_issue(issues, "error", "subgraph titles containing <br/> must be quoted")

    if re.search(r"stroke-dasharray:\s*\d+,\d+", body) and not re.search(
        r"stroke-dasharray:\s*\d+\\,\d+", body
    ):
        add_issue(issues, "warning", "escape comma in stroke-dasharray, e.g. `5\\,5`")

    if diagram_type == "sequenceDiagram" and re.search(r"->>.*:.*(?<!#59);", body):
        add_issue(
            issues,
            "warning",
            "literal semicolons in sequence messages should use `#59;`",
        )

    for bad, good in NON_CANONICAL_SYMBOLS.items():
        if bad in text:
            add_issue(
                issues,
                "warning",
                f"non-canonical symbol `{bad}`; prefer `{good}` from shared Typst notation",
            )

    # Warn on \\mathrm subscripts written as raw English with underscores outside math conventions.
    if re.search(r"\$\$.*_[a-zA-Z]{3,}.*\$\$", text, re.DOTALL):
        # Do not hard-fail; this catches many false positives in texttt labels.
        add_issue(
            issues,
            "info",
            "check long raw subscripts; thesis math should usually use `_{\\mathrm{...}}`",
        )

    # Basic balance checks.
    if text.count("$$") % 2 != 0:
        add_issue(issues, "error", "unbalanced `$$` delimiters")
    if text.count('"') % 2 != 0:
        add_issue(issues, "warning", "odd number of double quotes; check quoted labels")

    return issues


def run_mmdc(path: Path, output: Path | None) -> tuple[int, str]:
    """Render through the canonical repository-local Mermaid wrapper."""
    if output is None:
        output = path.with_suffix(".lint.svg")
    wrapper = Path(__file__).with_name("render_mermaid.sh")
    cmd = [str(wrapper), str(path), str(output)]
    proc = subprocess.run(
        cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90
    )
    return proc.returncode, proc.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint ARIA-NBV Mermaid thesis figures")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--render", action="store_true", help="also run mmdc if available"
    )
    parser.add_argument("--render-output", type=Path, default=None)
    args = parser.parse_args()

    total_errors = 0
    total_warnings = 0

    for path in args.files:
        text = path.read_text(encoding="utf-8")
        issues = lint_text(text, path)
        print(f"\n{path}")
        print("-" * len(str(path)))
        if not issues:
            print("OK: no lint issues")
        for severity, message in issues:
            print(f"{severity.upper()}: {message}")
            if severity == "error":
                total_errors += 1
            elif severity == "warning":
                total_warnings += 1

        if args.render:
            code, output = run_mmdc(path, args.render_output)
            if code == 0:
                print("RENDER: OK")
            elif code == 127:
                print(f"RENDER: SKIPPED: {output}")
            else:
                print("RENDER: ERROR")
                print(output)
                total_errors += 1

    print(f"\nSummary: {total_errors} error(s), {total_warnings} warning(s)")
    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
