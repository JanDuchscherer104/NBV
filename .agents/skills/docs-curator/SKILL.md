---
name: docs-curator
description: Use when ARIA-NBV work changes public docs, Typst/Quarto narrative, bibliography, navigation, or the public/internal docs boundary.
metadata:
  mode: implementation
  not_when:
    - "localized typo with no source-of-truth risk"
    - "memory-only, backlog-only, or KG-consolidation work"
    - "internal operator-reference edits outside public docs"
  handoff_to:
    - "agents-db for backlog-only changes"
    - "aria-litkg-memory for KG-backed claim checks or consolidation"
    - "owning skill for internal operator references"
  evidence_required:
    - "docs/AGENTS.md and source-order owner for changed claims"
    - "render or outline check for non-trivial docs edits"
    - "claim-check output for advisor-facing claims"
  applies_to:
    - "README.md"
    - "SETUP.md"
    - "docs/**"
  triggers:
    - "Quarto"
    - "Typst"
    - "bibliography"
    - "public/internal docs boundary"
  must_read:
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md"
    - ".agents/references/verification_matrix.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - "docs/contents/thesis/roadmap.qmd"
    - "docs/contents/thesis/questions.qmd"
    - "docs/references.bib"
  context7_refs:
    - "/websites/quarto"
    - "/websites/typst_app"
  literature_refs:
    - "docs/contents/literature/index.qmd"
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
  verification:
    - "make qmd-frontmatter-check for Quarto docs"
    - "cd docs && quarto render <page.qmd> for changed pages"
    - "make kg-claim-check KG_CLAIM=\"<claim>\" for advisor-facing claims"
---

# Docs Curator

## When To Use

Use this skill for reader-facing docs, bibliography, Typst/Quarto narrative,
navigation, and public/internal boundary decisions.

## Read First

1. `docs/AGENTS.md`
2. `.agents/references/source_order.md`
3. The source that owns the touched role, as defined by source order
4. The exact behavior or workflow owner named by source order

## Rules

- Keep public Quarto docs reader-facing; internal agent guidance, generated
  context, raw scratch history, and OMX runtime notes stay under `.agents/`.
- Run litkg claim checks for advisor-facing proposal, roadmap,
  research-question, or literature-synthesis claims.
- Link to the exact source-order owner instead of repeating long explanations.
- Keep bibliography additions in `docs/references.bib`.
- Use QMD frontmatter to classify rendered pages:
  `phase: thesis | seminar | archive | generated`,
  `audience: public | advisor | developer | agent`,
  `status: current | planned | scratch | deprecated`, and
  `owner: paper | docs | code | agent | generated | jan`.
- Do not render `audience: agent` pages under `docs/contents/**`; raw internal
  archive and backlog history belongs under `.agents/archive/docs/`.
- Keep all retained public QMD files renderable. Only curated archive summaries
  belong under `docs/contents/archive/`.

## Verification

- `cd docs && quarto render contents/thesis/roadmap.qmd contents/thesis/questions.qmd` for roadmap/question edits
- `cd docs && typst compile typst/seminar_paper/main.typ --root .` for paper edits
- `cd docs && typst compile typst/seminar_slides/<file>.typ --root .` for slide edits
- `scripts/nbv_qmd_outline.sh --compact` for public navigation checks
- `make qmd-frontmatter-check` for rendered QMD taxonomy changes
- `make check-agent-memory` for `.agents/` or canonical-memory edits
