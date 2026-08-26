#!/usr/bin/env python3
"""Select the root CI families affected by a NUL-delimited path list."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

FAMILIES = ("scaffold", "package", "docs")

FULL_PATHS = {
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    "Makefile",
    "aria_nbv/pyproject.toml",
    "aria_nbv/uv.lock",
    "scripts/ci_impact.py",
    "scripts/tests/test_ci_impact.py",
}

SCAFFOLD_PATHS = {
    "AGENTS.md",
    "scripts/agents_db.py",
    "scripts/agent_status.py",
    "scripts/check_graphify_freshness.py",
    "scripts/graphify_worktree_seed.py",
    "scripts/reconcile_graphify_worktree.py",
    "scripts/setup_codex_worktree_env.sh",
    "scripts/scaffold_audit.py",
    "scripts/skill_sources.py",
    "scripts/scaffold/run_routing_trials.py",
    "scripts/scaffold/fixtures/routing_prompts.jsonl",
    "scripts/scaffold/fixtures/routing.json",
    "scripts/scaffold/fixtures/routing_trial_report.schema.json",
    "scripts/scaffold/fixtures/routing_verdict.schema.json",
    "scripts/setup_worktree_env.sh",
    "scripts/validate_agent_memory.py",
    "scripts/debrief_index.py",
    "scripts/new_debrief.py",
    "scripts/debrief_nudge.sh",
    "scripts/tests/test_agent_governance_g002.py",
    "scripts/tests/test_debrief_index.py",
    "scripts/tests/test_validate_agent_memory_threads.py",
    "scripts/tests/test_routing_trials.py",
    "scripts/tests/test_agent_status.py",
    "scripts/tests/test_graphify_freshness.py",
    "scripts/tests/test_graphify_upstream_skill.py",
    "scripts/tests/test_graphify_worktree_seed.py",
    "scripts/tests/test_skill_sources.py",
    "scripts/tests/test_reconcile_graphify_worktree.py",
    "scripts/tests/test_graphify_session_readiness.py",
    "scripts/tests/test_setup_worktree_env.sh",
}

DOCS_PATHS = {
    ".graphifyignore",
    "README.md",
    "SETUP.md",
    "scripts/build_graphify_projection.py",
    "scripts/literature_catalog.py",
    "scripts/tests/test_build_graphify_projection.py",
    "scripts/tests/test_thesis_literature_provenance.py",
    "scripts/tests/test_quarto_generate_api_docs.sh",
    "scripts/validate_qmd_frontmatter.py",
}


def select_families(paths: list[str]) -> set[str]:
    """Return affected CI families, failing closed for any unknown path."""
    selected: set[str] = set()
    unknown = False

    for path in paths:
        if path in FULL_PATHS:
            return set(FAMILIES)

        matched = False
        if (
            path.startswith(".agents/")
            and not path.startswith(
                (
                    ".agents/skills/typst-authoring/",
                    ".agents/skills/academic-writing/",
                    ".agents/skills/literature-research/",
                    ".agents/skills/scientific-review/",
                )
            )
            or path in SCAFFOLD_PATHS
        ):
            selected.add("scaffold")
            matched = True
        if path == ".agents/skills/README.md":
            selected.add("docs")
            matched = True
        if path.startswith(
            (
                ".agents/skills/typst-authoring/",
                ".agents/skills/academic-writing/",
                ".agents/skills/literature-research/",
                ".agents/skills/scientific-review/",
            )
        ):
            # Authoring guidance changes can alter docs behavior even though
            # the skill itself lives under the scaffold namespace. They also
            # own tested routing and phase boundaries, so keep both gates live.
            selected.add("docs")
            selected.add("scaffold")
            matched = True
        if path.startswith("aria_nbv/") or path.startswith(".configs/"):
            selected.add("package")
            matched = True
        if path.startswith("docs/") or path in DOCS_PATHS:
            selected.add("docs")
            matched = True

        unknown = unknown or not matched

    return set(FAMILIES) if unknown else selected


def parse_nul_paths(raw: bytes) -> list[str]:
    """Decode a non-empty, NUL-terminated path stream from ``git diff -z``."""
    if not raw or not raw.endswith(b"\0"):
        raise ValueError("expected a non-empty NUL-terminated path list")
    paths = [item.decode("utf-8") for item in raw[:-1].split(b"\0")]
    if any(not path for path in paths):
        raise ValueError("path list contains an empty entry")
    return paths


def _write_outputs(selected: set[str], output_path: Path) -> None:
    with output_path.open("a", encoding="utf-8") as output:
        for family in FAMILIES:
            output.write(f"{family}={str(family in selected).lower()}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="select every family")
    parser.add_argument(
        "--github-output",
        type=Path,
        default=os.environ.get("GITHUB_OUTPUT"),
        help="append GitHub Actions step outputs to this file",
    )
    args = parser.parse_args()

    try:
        selected = (
            set(FAMILIES)
            if args.full
            else select_families(parse_nul_paths(sys.stdin.buffer.read()))
        )
    except (UnicodeDecodeError, ValueError) as error:
        parser.error(str(error))

    if args.github_output is not None:
        _write_outputs(selected, args.github_output)
    print("selected CI families: " + ", ".join(sorted(selected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
