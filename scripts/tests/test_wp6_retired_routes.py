#!/usr/bin/env python3
"""Reject active LitKG and broad generated-context routes after WP6."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ABSENT_PATHS = {
    ".agents/external/litkg-rs",
    ".agents/kg",
    ".agents/references/litkg_quick_reference.md",
    ".agents/skills/aria-litkg-memory",
    ".agents/skills/semantic-scholar-litkg",
    ".agents/skills/aria-nbv-context/references/context_map.md",
    ".configs/litkg.toml",
    ".claude/commands/kg-claim-check.md",
    ".claude/commands/context-refresh.md",
    "scripts/kg",
    "scripts/nbv_context_index.sh",
    "scripts/nbv_literature_index.sh",
    "scripts/nbv_literature_search.sh",
}
ACTIVE_SCAN_ROOTS = [
    "AGENTS.md",
    "CLAUDE.md",
    "Makefile",
    ".claude",
    ".codex/hooks.example.json",
    ".gemini/settings.json",
    ".agents/AGENTS_INTERNAL_DB.md",
    ".agents/issues.toml",
    ".agents/todos.toml",
    ".agents/refactors.toml",
    ".agents/references",
    ".agents/skills",
    "aria_nbv/AGENTS.md",
    "docs/AGENTS.md",
    "scripts",
]
FORBIDDEN = re.compile(
    r"litkg|aria-litkg|semantic-scholar-litkg|code-review-aria-nbv|diagnose-aria|"
    r"entity-aware-rri|nbv-geometry-contracts|counterfactual-rollout-planner|"
    r"make\s+kg-|scripts/kg/|\.agents/kg|"
    r"context-heavy|context-(?:index|package|modules|classes|functions|match|literature-index|uml|docstrings|tree)|"
    r"make\s+context(?:\s|$)|context_map\.md|docs/_generated/context/(?:source_index|literature_index|data_contracts|context_snapshot)",
    re.IGNORECASE,
)
ALLOW_PATHS = {
    ".agents/baselines/scaffold_wp6_capability_dispositions.csv",
    "scripts/scaffold_audit.py",
    "scripts/validate_scaffold_wp0_baseline.py",
    "scripts/tests/test_wp6_retired_routes.py",
}
HISTORICAL_LEDGER_LITERAL = re.compile(
    r'^\s*"(?:decisions-litkg|gotchas-litkg|project-litkg-infrastructure)",?\s*$'
)


def tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "--", *ACTIVE_SCAN_ROOTS],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [ROOT / line for line in output.splitlines() if line]


def main() -> int:
    for path in ABSENT_PATHS:
        assert not (ROOT / path).exists(), f"retired path remains: {path}"
    assert "litkg-rs" not in (ROOT / ".gitmodules").read_text(encoding="utf-8").lower()
    findings: list[str] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW_PATHS or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if (
                rel == "scripts/validate_agent_memory.py"
                and HISTORICAL_LEDGER_LITERAL.match(line)
            ):
                continue
            if FORBIDDEN.search(line):
                findings.append(f"{rel}:{line_no}:{line.strip()}")
    assert not findings, "active retired routes remain:\n" + "\n".join(findings)
    print("WP6 retired-route scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
