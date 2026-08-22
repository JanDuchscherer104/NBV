"""Direct-source regression gates for the completed ownership migration."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MIGRATION_RECEIPT = (
    ROOT / ".agents/memory/history/2026/08/2026-08-16_ownership_migration_receipt.md"
)

RETIRED_SOURCES = (
    ".agents/references/source_order.md",
    "docs/contents/thesis/roadmap.qmd",
    "docs/contents/thesis/questions.qmd",
    "docs/contents/thesis/m1_contract_report.qmd",
    ".agents/memory/state/PROJECT_STATE.md",
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
)

CONTEXT_INITIALIZATION_OWNERS = (
    "docs/typst/shared/symbols.typ",
    "docs/typst/shared/equations.typ",
    "docs/typst/shared/glossary.typ",
    "docs/typst/glossary/",
    "docs/literature/sources.jsonl",
    "docs/references.bib",
    "docs/references-qh.bib",
    "docs/contents/literature/",
    "docs/typst/thesis/sections/",
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

EXPECTED_QMD_PAGES = {
    "archive/index.qmd",
    "archive/main_seminar_findings.qmd",
    "ase_dataset.qmd",
    "diagrams.qmd",
    "glossary.qmd",
    "ideas.qmd",
    "literature/3dgs_instance_nbv.qmd",
    "literature/active_3dgs_nbv.qmd",
    "literature/efm3d.qmd",
    "literature/gen_nbv.qmd",
    "literature/hestia.qmd",
    "literature/index.qmd",
    "literature/pb_nbv.qmd",
    "literature/project_aria.qmd",
    "literature/rl_planning.qmd",
    "literature/scene_script.qmd",
    "literature/scone_fisherrf.qmd",
    "literature/vin_nbv.qmd",
    "resources.qmd",
    "setup.qmd",
    "theory/candidate_sampling_target_selection.qmd",
    "theory/candidate_view_dependence.qmd",
    "theory/efm3d_scene_embeddings.qmd",
    "theory/nbv_background.qmd",
    "theory/rl_planning.qmd",
    "theory/rri_theory.qmd",
    "theory/semi-dense-pc.qmd",
    "theory/surface_metrics.qmd",
}

HISTORICAL_PREFIXES = (
    ".agents/archive/",
    ".agents/memory/history/",
    ".agents/memory/transcripts/",
    ".omx/",
    "docs/typst/thesis_slides/",
)

DERIVED_HISTORICAL_EVIDENCE_PATHS = {
    ".agents/memory/index/debriefs.jsonl",
}

MIGRATION_TEST_PATHS = {
    "scripts/tests/test_agent_governance_g002.py",
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

SOURCE_ORDER_REFERENCE_PROVENANCE = {
    ".omx/plans/graphify-thin-adapter.md",
    ".omx/plans/pr50-graphify-mandatory-upstream-first.md",
    ".omx/plans/prd-aria-nbv-domain-skill-distillation.md",
    ".omx/plans/prd-thin-root-nested-agents-rewrite.md",
    ".omx/plans/test-spec-aria-nbv-domain-skill-distillation.md",
    ".omx/plans/test-spec-aria-nbv-ownership-branch-consolidation.md",
    ".omx/specs/autoresearch-agent-scaffold-external-best-practices-20260730/report.md",
    ".omx/specs/deep-interview-aria-nbv-agent-scaffold-target-state.md",
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


def _is_historical_evidence_path(relative: str) -> bool:
    return relative.startswith(HISTORICAL_PREFIXES) or (
        relative in DERIVED_HISTORICAL_EVIDENCE_PATHS
    )


def _frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    parts = text.split("\n---\n", 1)
    assert len(parts) == 2
    return parts[0].removeprefix("---\n")


def _markdown_table_rows(text: str, header: str) -> list[list[str]]:
    lines = text.splitlines()
    start = lines.index(header)
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def test_retired_sources_are_absent() -> None:
    assert not [path for path in RETIRED_SOURCES if (ROOT / path).exists()]


def test_context_skill_owns_hierarchy_and_initialization_map() -> None:
    context = (ROOT / ".agents/skills/aria-nbv-context/SKILL.md").read_text(
        encoding="utf-8"
    )

    assert len(context.splitlines()) <= 150
    assert not [
        owner for owner in CONTEXT_INITIALIZATION_OWNERS if f"`{owner}`" not in context
    ]
    for heading in ("## Owner Hierarchy", "## Conflict Rule", "## Capture Rule"):
        assert heading in context


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


def test_expected_qmd_page_manifest_is_exact() -> None:
    contents_root = ROOT / "docs/contents"
    observed = {
        path.relative_to(contents_root).as_posix()
        for path in contents_root.rglob("*.qmd")
    }
    assert observed == EXPECTED_QMD_PAGES
    assert (
        not {
            "thesis/questions.qmd",
            "thesis/roadmap.qmd",
            "thesis/m1_contract_report.qmd",
        }
        & observed
    )


def test_theory_qmd_matrix_covers_every_thinned_page() -> None:
    text = MIGRATION_RECEIPT.read_text(encoding="utf-8")
    rows = _markdown_table_rows(
        text,
        "| Theory page | Disposition | Unique retained value | Canonical destination | Inbound links | Citation disposition |",
    )
    assert len(rows) == len(THEORY_PAGES)
    assert {row[0].strip("`") for row in rows} == THEORY_PAGES
    for row in rows:
        assert len(row) == 6
        assert row[1] == "thin"
        assert all(cell and cell not in {"-", "—"} for cell in row[2:])
        assert "docs/" in row[3]


def test_conditional_rq_experiments_have_separate_backlog_records() -> None:
    text = MIGRATION_RECEIPT.read_text(encoding="utf-8")
    rows = _markdown_table_rows(
        text,
        "| Scope | Scientific owner | Active backlog record | Entry gate |",
    )
    observed = {row[0]: row for row in rows}
    assert set(observed) == {
        "RQ5 online discrete bridge",
        "RQ6 continuous/simulator escalation",
    }
    assert "todo-095" in observed["RQ5 online discrete bridge"][2]
    assert {"todo-006", "todo-038"} <= set(
        re.findall(r"todo-\d{3}", observed["RQ6 continuous/simulator escalation"][2])
    )


def test_active_sources_do_not_reference_retired_paths() -> None:
    violations: list[str] = []
    for relative in _tracked_paths():
        if relative in MIGRATION_TEST_PATHS or relative == ".agents/resolved.toml":
            continue
        if _is_historical_evidence_path(relative):
            continue
        path = ROOT / relative
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for retired in RETIRED_SOURCES:
            if retired in text:
                violations.append(f"{relative}: {retired}")
    assert not violations


def test_only_debrief_index_is_derived_historical_evidence() -> None:
    assert _is_historical_evidence_path(".agents/memory/index/debriefs.jsonl")
    assert not _is_historical_evidence_path(".agents/memory/index/owners.jsonl")


def test_generated_omx_inventory_is_not_tracked() -> None:
    tracked = _tracked_paths()
    assert ".omx/specs/ownership-branch-consolidation-inventory.json" not in tracked
    assert ".omx/specs/ownership-branch-consolidation-inventory.md" not in tracked


def _retired_reference_aliases() -> set[str]:
    aliases: set[str] = set()
    for retired in RETIRED_SOURCES:
        path = Path(retired)
        aliases.update({retired, path.name, path.as_posix()})
        if retired != ".agents/references/source_order.md":
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
            if relative in SOURCE_ORDER_REFERENCE_PROVENANCE and alias in {
                ".agents/references/source_order.md",
                "source_order.md",
                (ROOT / ".agents/references/source_order.md").as_posix(),
            }:
                continue
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
        # RQ section labels are canonical Typst anchors.  Do not silently
        # accept the retired bare ``#rqN`` fragments: that would let glossary
        # links drift back to the pre-migration owner.
        observed = [
            anchor.removeprefix("ssec:")
            for anchor in re.findall(
                r"research-questions\.typ#(ssec:rq\d+)", match.group(1)
            )
        ]
        assert len(observed) == len(set(observed)), f"{term}: duplicate RQ links"
        assert set(observed) == expected_rqs, term


def test_glossary_theory_links_target_existing_anchors() -> None:
    """Do not retain fragments removed when theory pages become thin navigation."""
    text = (ROOT / "docs/typst/shared/glossary.typ").read_text(encoding="utf-8")
    links = set(re.findall(r'"(docs/contents/theory/[^"#]+\.qmd#[^"]+)"', text))
    for link in links:
        relative, anchor = link.split("#", 1)
        target = (ROOT / relative).read_text(encoding="utf-8")
        assert f"{{#{anchor}}}" in target, link


def test_scientific_sources_keep_glossary_renderer_and_bibliography_owners_distinct() -> (
    None
):
    context = (ROOT / ".agents/skills/aria-nbv-context/SKILL.md").read_text(
        encoding="utf-8"
    )
    glossary_source = ROOT / "docs/typst/shared/glossary.typ"
    glossary_renderer = ROOT / "docs/contents/glossary.qmd"
    acquisition_owner = ROOT / "docs/literature/sources.jsonl"
    citation_owners = (
        ROOT / "docs/references.bib",
        ROOT / "docs/references-qh.bib",
    )
    synthesis_owner = ROOT / "docs/contents/literature"
    claim_owner = ROOT / "docs/typst/thesis/sections"
    assert glossary_source.is_file()
    assert glossary_renderer.is_file()
    assert acquisition_owner.is_file()
    assert all(path.is_file() for path in citation_owners)
    assert synthesis_owner.is_dir()
    assert claim_owner.is_dir()
    assert glossary_source != glossary_renderer
    assert acquisition_owner not in citation_owners
    assert len(set(citation_owners)) == 2
    assert "Canonical ARIA-NBV glossary source" in glossary_source.read_text(
        encoding="utf-8"
    )
    assert "Generated" in glossary_renderer.read_text(encoding="utf-8")
    assert acquisition_owner.suffix == ".jsonl"
    assert all(path.suffix == ".bib" for path in citation_owners)
    assert "acquisition/relevance metadata" in context
    assert "citation identities" in context
    assert "review synthesis" in context
    assert "active claim placement" in context
    for owner in (
        "docs/literature/sources.jsonl",
        "docs/references.bib",
        "docs/references-qh.bib",
        "docs/contents/literature/",
        "docs/typst/thesis/sections/",
    ):
        assert f"`{owner}`" in context
