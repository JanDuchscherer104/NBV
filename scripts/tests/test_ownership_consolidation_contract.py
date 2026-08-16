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
    "scripts/codex_transcript_extract.py",
    "aria_nbv/tests/agent_memory/test_codex_transcript_extract.py",
}

RETIRED_REFERENCE_PROVENANCE = {
    ".omx/plans/prd-aria-nbv-ownership-branch-consolidation.md",
    ".omx/plans/test-spec-thin-root-nested-agents-rewrite.md",
    ".omx/specs/autoresearch-agent-scaffold-rework-20260729/report.md",
    ".omx/specs/ownership-branch-consolidation-successor-spec.md",
}

REFERENCE_EXCLUDED_PREFIXES = (
    ".agents/archive/",
    ".agents/memory/transcripts/",
    ".omx/context/",
    ".omx/interviews/",
    "docs/contents/archive/",
)

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


def _retired_reference_aliases() -> set[str]:
    aliases: set[str] = set()
    for retired in RETIRED_SOURCES:
        path = Path(retired)
        aliases.update({retired, path.name, path.as_posix()})
        aliases.add(path.parent.as_posix() + "/")
        aliases.add((ROOT / path).as_posix())
    return aliases


def test_active_omx_and_maintained_slides_scope_retired_references() -> None:
    """Scan active planning/slides with path aliases, allowing only provenance."""
    prefixes = (".omx/plans/", ".omx/specs/", "docs/typst/thesis_slides/")
    aliases = _retired_reference_aliases()
    violations: list[str] = []
    for relative in sorted(_tracked_paths()):
        if not relative.startswith(prefixes):
            continue
        path = ROOT / relative
        if path.suffix.lower() not in {".md", ".typ", ".json", ".html"}:
            continue
        if relative in RETIRED_REFERENCE_PROVENANCE or relative.startswith(
            REFERENCE_EXCLUDED_PREFIXES
        ):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for alias in aliases:
            if alias in text:
                violations.append(f"{relative}: {alias}")
    assert not violations


def test_glossary_rq_links_match_the_six_tier_semantics() -> None:
    """Keep term links aligned with objective, representation, and support tiers."""
    text = (ROOT / "docs/typst/shared/glossary.typ").read_text(encoding="utf-8")
    expected = {
        "target-conditioned-scorer": {"rq2", "rq3"},
        "observed-target-selection": {"rq3"},
        "predicted-target-q": {"rq2", "rq3", "rq5"},
        "ground-truth-target-evaluation": {"rq1", "rq3"},
        "finite-candidate-action-set": {"rq2", "rq4"},
        "finite-horizon-return": {"rq2"},
        "finite-horizon-q-function": {"rq2"},
        "oriented-bounding-box": {"rq3"},
        "candidate-view": {"rq4"},
    }
    for term, expected_rqs in expected.items():
        match = re.search(
            rf'anchor: "term-{re.escape(term)}".*?internal_links: \((.*?)\),',
            text,
            flags=re.DOTALL,
        )
        assert match is not None, term
        observed = re.findall(r"research-questions\.typ#(rq\d+)", match.group(1))
        assert len(observed) == len(set(observed)), f"{term}: duplicate RQ links"
        assert set(observed) == expected_rqs, term
