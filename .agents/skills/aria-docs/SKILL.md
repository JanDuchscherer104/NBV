---
name: aria-docs
description: Use for ARIA-NBV Quarto, Typst thesis or slides, citations, scientific figures, tables, shared notation, or Mermaid diagrams.
metadata:
  mode: implementation
  not_when:
    - "a thesis-scope or advisor-facing research decision is unresolved"
    - "a persistent multi-surface build failure needs diagnostic isolation"
    - "Python API docstrings are the primary output"
  handoff_to:
    - "plan-grill for unresolved thesis scope or claim boundaries"
    - "python-docstrings for Python API documentation"
    - "rerun-nbv-inspector for Rerun recording, camera/frustum, frame, or blueprint implementation"
    - "specialized diagnostic capability for persistent build or render failures"
  evidence_required:
    - "nearest docs owner, target imports, and adjacent narrative"
    - "shared notation and glossary owners for new symbols, equations, or durable terms"
    - "citation source and calibrated wording for research claims"
    - "reproducible source, frame, units, view, and provenance for scientific figures"
    - "compile plus rendered-page inspection for non-trivial prose, visual, math, or slide edits"
  applies_to:
    - "docs/**"
    - "tools/mermaid/**"
  triggers:
    - "Quarto documentation"
    - "Typst thesis or slides"
    - "shared notation or Glossarium"
    - "scientific figure or table"
    - "citation or scientific figure"
    - "Mermaid diagram"
  must_read:
    - "docs/AGENTS.md"
    - ".agents/skills/aria-docs/references/workflow.md"
    - ".agents/references/direct_source_claim_checklist.md for advisor-facing claims"
  canonical_sources:
    - "docs/AGENTS.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared"
    - "docs/references.bib"
    - ".agents/skills/aria-docs/references/typst.md"
    - ".agents/skills/aria-docs/references/thesis-writing.md"
    - ".agents/skills/aria-docs/references/visuals.md"
    - ".agents/skills/aria-docs/references/mermaid.md"
    - "tools/mermaid/references/aria_mermaid_style.md"
    - "tools/mermaid/references/aria_symbol_map.yaml"
    - ".agents/references/thesis_code_links.md"
    - ".agents/references/direct_source_claim_checklist.md"
  context7_refs:
    - "/websites/typst_app"
    - "/websites/quarto"
    - "/mermaid-js/mermaid"
  literature_refs:
    - "docs/literature/sources.jsonl"
    - "docs/references.bib"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
  verification:
    - "make qmd-frontmatter-check for Quarto ownership changes"
    - "focused Typst or Quarto compile plus rendered-page inspection"
    - "python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd> for Mermaid edits"
---

# ARIA Docs

Choose one branch in `references/workflow.md`. Read only that branch's owners
and reference file; do not load the full documentation stack by default.

## Branches

| Task | Read after `workflow.md` |
| --- | --- |
| Quarto page, navigation, or public boundary | Target page and `docs/AGENTS.md` |
| Typst syntax, notation, glossary, equation, or compile loop | `references/typst.md` |
| Thesis/proposal prose, section, claim, or citation | `references/thesis-writing.md` |
| Figure, table, caption, scientific visualization, or slide | `references/visuals.md` |
| Mermaid source or export | `references/mermaid.md` |

## Invariants

- Exact document, bibliography, shared notation, package, code, and test
  sources remain authoritative; this skill owns workflow and authoring policy.
- Reuse `docs/typst/shared` before creating document-local terms, symbols, or
  equations. Glossarium owns prose terms; shared symbol/equation facades own
  mathematical notation.
- Preserve the public/internal boundary and the active-versus-historical
  document roles in `docs/AGENTS.md`.
- Claims use calibrated language and exact source evidence. Figures preserve
  construction provenance and geometry/view metadata.
- A successful compile is not visual QA. Inspect affected rendered pages for
  legibility, clipping, math attachment, references, captions, and layout.

Stop when the owning source is updated, the narrow checks pass, and render
evidence or an exact environment blocker is recorded.
