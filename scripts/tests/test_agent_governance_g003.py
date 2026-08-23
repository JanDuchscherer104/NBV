#!/usr/bin/env python3
"""Focused migration checks for G003 owner-specific preferences."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "61a93f19792433f6d94f265e5e43d5f08d80fccc"

PYTHON_OWNER = ".agents/skills/python-standards/references/general_conventions.md"
SKILLS_OWNER = ".agents/skills/README.md"
APP_OWNER = "aria_nbv/aria_nbv/app/AGENTS.md"
ROOT_GUIDANCE = "AGENTS.md"
HUMAN_INTENT = ".agents/references/human_owner_intent.md"


def _current(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _baseline(relative: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{BASE}:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _contains_all(text: str, *phrases: str) -> bool:
    normalized = re.sub(r"\s+", " ", text.lower())
    return all(re.sub(r"\s+", " ", phrase.lower()) in normalized for phrase in phrases)


def _heading_section(text: str, heading: str) -> str:
    """Return one Markdown heading's body, excluding following peer sections."""
    lines = text.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"#{1,6} " + re.escape(heading), line.strip())
    )
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#{1,6}) ", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return "\n".join(lines[start:end])


def _scientific_contract(text: str) -> bool:
    return _contains_all(
        text,
        "what it means",
        "definition",
        "units",
        "assumptions",
        "formula or computational transform",
        "normalization/denominator",
        "intuition",
        "failure modes",
        "exact notation",
        "links to canonical",
        "canonical equation",
        "symbol",
        "glossary",
        "source owners",
        "raw",
        "exact",
        "tables",
        "exports",
        "subordinate",
        "interpretation",
        "collapsed",
        "directly beneath",
    )


def test_python_owner_migrates_composition_and_helper_locality_contract() -> None:
    baseline = _baseline(PYTHON_OWNER)
    candidate = _current(PYTHON_OWNER)
    baseline_core_rules = _heading_section(baseline, "Core Rules")
    candidate_core_rules = _heading_section(candidate, "Core Rules")

    assert (
        "Instantiate runtime objects through config `.setup_target()`"
        in baseline_core_rules
    )
    assert not _contains_all(
        baseline_core_rules,
        "composition edges",
        "already-constructed dependencies",
        "do not construct runtime objects internally",
    )
    assert not _contains_all(
        baseline_core_rules,
        "single-consumer private helpers",
        "multiple demonstrated consumers",
        "hypothetical generic utility buckets",
    )

    assert _contains_all(
        candidate_core_rules,
        "call config `.setup_target()` at composition edges",
        "CLI",
        "Lightning",
        "pipeline",
        "domain",
        "forward",
        "scoring",
        "methods consume",
        "already-constructed dependencies",
        "do not construct runtime objects internally",
    )
    assert _contains_all(
        candidate_core_rules,
        "single-consumer private helpers local",
        "inline trivial helpers",
        "multiple demonstrated consumers",
        "lowest shared domain owner",
        "hypothetical generic utility buckets",
    )
    assert "domain methods call `.setup_target()`" not in candidate
    assert (
        "Instantiate runtime objects through config `.setup_target()`" not in candidate
    )


def test_skills_owner_migrates_pointer_and_upstream_maintenance_contract() -> None:
    baseline = _baseline(SKILLS_OWNER)
    candidate = _current(SKILLS_OWNER)
    baseline_references = _heading_section(baseline, "Conditional references")
    candidate_references = _heading_section(candidate, "Conditional references")
    baseline_upstream = _heading_section(baseline, "Upstream skills")
    candidate_upstream = _heading_section(candidate, "Upstream skills")

    assert not _contains_all(
        baseline_references,
        "pointer preservation",
        "names the branch and target",
        "bounded refresh/check",
    )
    assert not _contains_all(
        baseline_upstream,
        "exact upstream body",
        "pinned release/commit reference",
        "refresh/check procedure",
    )

    assert _contains_all(
        candidate_references,
        "conditional references",
        "pointer preservation",
        "names the branch and target strongly enough",
        "load the moved detail",
    )
    assert _contains_all(
        candidate_upstream,
        "preserve its upstream frontmatter",
        "all upstream bytes",
        "exact upstream body",
        "pinned release/commit reference",
        "ARIA-owned companion",
        "maintenance surface outside the bundle",
        "byte-identical",
        "bounded refresh/check procedure",
    )


def test_app_owner_migrates_interpretation_and_operational_exception_contract() -> None:
    baseline = _baseline(APP_OWNER)
    candidate = _current(APP_OWNER)
    baseline_interaction = _heading_section(baseline, "Interaction Contract")
    candidate_interaction = _heading_section(candidate, "Interaction Contract")

    assert not _scientific_contract(baseline_interaction)
    assert _scientific_contract(candidate_interaction)
    assert _contains_all(
        candidate_interaction,
        "operational counts",
        "provenance",
        "concise narrative",
        "do not invent equations",
    )


def test_migration_keeps_contracts_at_their_designated_owners() -> None:
    root_guidance = _current(ROOT_GUIDANCE)
    human_intent = _current(HUMAN_INTENT)
    forbidden_duplications = (
        "already-constructed dependencies",
        "single-consumer private helpers",
        "bounded refresh/check procedure",
        "exact upstream body",
        "normalization/denominator",
        "do not invent equations",
    )
    for phrase in forbidden_duplications:
        assert phrase not in root_guidance.lower()
        assert phrase not in human_intent.lower()


if __name__ == "__main__":
    tests = [
        value for name, value in sorted(globals().items()) if name.startswith("test_")
    ]
    for test in tests:
        test()
    print(f"G003 governance migration tests passed: {len(tests)}")
