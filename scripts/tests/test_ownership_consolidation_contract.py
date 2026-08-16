"""Direct-source regression gates for the completed ownership migration."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RETIRED_SOURCES = (
    "docs/contents/thesis/roadmap.qmd",
    "docs/contents/thesis/questions.qmd",
    "docs/contents/thesis/m1_contract_report.qmd",
    ".agents/memory/state/PROJECT_STATE.md",
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
)

TYPST_OWNERS = (
    "docs/typst/thesis/sections/01-research-questions.typ",
    "docs/typst/thesis/development/roadmap.typ",
    "docs/typst/thesis/development/m1-contract-report.typ",
)

THEORY_PAGES = {
    "candidate_sampling_target_selection.qmd",
    "candidate_view_dependence.qmd",
    "efm3d_scene_embeddings.qmd",
    "nbv_background.qmd",
    "rl_planning.qmd",
    "rri_theory.qmd",
    "semi-dense-pc.qmd",
    "surface_metrics.qmd",
}

HISTORICAL_PREFIXES = (
    ".agents/archive/",
    ".agents/memory/history/",
    ".agents/memory/transcripts/",
    ".omx/",
    "docs/typst/thesis_slides/",
)

MIGRATION_TEST_PATHS = {
    "scripts/tests/test_ownership_consolidation_contract.py",
    "scripts/tests/test_validate_agent_memory_retired.py",
    "scripts/validate_agent_memory.py",
}

TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".qmd",
    ".sh",
    ".toml",
    ".typ",
    ".txt",
    ".yaml",
    ".yml",
}


def _tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    payload = result.stdout.rstrip(b"\0")
    paths = [item.decode("utf-8") for item in payload.split(b"\0")] if payload else []
    return [path for path in paths if (ROOT / path).is_file()]


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    parts = text.split("\n---\n", 1)
    assert len(parts) == 2
    return parts[0].removeprefix("---\n")


def test_retired_sources_are_absent() -> None:
    assert not [path for path in RETIRED_SOURCES if (ROOT / path).exists()]


def test_source_order_links_each_typst_owner() -> None:
    text = (ROOT / ".agents/references/source_order.md").read_text(encoding="utf-8")
    assert not [owner for owner in TYPST_OWNERS if f"`{owner}`" not in text]


def test_theory_pages_are_deprecated_navigation() -> None:
    theory_root = ROOT / "docs/contents/theory"
    observed = {path.name for path in theory_root.glob("*.qmd")}
    assert observed == THEORY_PAGES

    forbidden_owner_claim = re.compile(
        r"\b(?:canonical|current)\s+(?:theory|implementation|source)\s+owner\b"
        r"|\bowns?\s+(?:theory|implementation contract)\b",
        re.IGNORECASE,
    )
    for name in sorted(observed):
        text = (theory_root / name).read_text(encoding="utf-8")
        frontmatter = _frontmatter(text)
        assert re.search(r"(?m)^phase:\s*archive\s*$", frontmatter)
        assert re.search(r"(?m)^status:\s*deprecated\s*$", frontmatter)
        assert re.search(r"(?m)^owner:\s*docs\s*$", frontmatter)
        assert "docs/typst/thesis" in text or "../../typst/thesis" in text
        assert forbidden_owner_claim.search(text) is None


def test_active_sources_do_not_reference_retired_paths() -> None:
    violations: list[str] = []
    for relative in _tracked_paths():
        if relative in MIGRATION_TEST_PATHS or relative == ".agents/resolved.toml":
            continue
        if relative.startswith(HISTORICAL_PREFIXES):
            continue
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED_SOURCES:
            if retired in text:
                violations.append(f"{relative}: {retired}")
    assert not violations


def test_generated_omx_inventory_is_not_tracked() -> None:
    tracked = _tracked_paths()
    assert ".omx/specs/ownership-branch-consolidation-inventory.json" not in tracked
    assert ".omx/specs/ownership-branch-consolidation-inventory.md" not in tracked
    assert not [
        path
        for path in tracked
        if path.startswith(".omx/") and not path.endswith(".md")
    ]
