---
name: aria-docs
description: Use for ARIA-NBV Quarto, Typst, thesis prose, citations, scientific figures, Mermaid sources, and compile or render QA.
metadata:
  mode: implementation
  not_when:
    - "a thesis-scope or advisor-facing research decision is unresolved"
    - "a persistent multi-surface build failure needs diagnostic isolation"
    - "Python API docstrings are the primary output"
  handoff_to:
    - "plan-grill for unresolved thesis scope or claim boundaries"
    - "python-docstrings for Python API documentation"
    - "specialized diagnostic capability for persistent build or render failures"
  evidence_required:
    - "nearest docs owner, target imports, and adjacent narrative"
    - "citation source and calibrated wording for research claims"
    - "compile plus rendered-page inspection for non-trivial visual or math edits"
  applies_to:
    - "docs/**"
    - "tools/mermaid/**"
  triggers:
    - "Quarto documentation"
    - "Typst thesis"
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
    - "focused Typst or Quarto compile and rendered-page inspection"
    - "python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd> for Mermaid edits"
---

# ARIA Docs

Choose the Quarto, Typst, or Mermaid branch in `references/workflow.md`, read
only its listed owners, and keep durable scientific truth in the touched docs,
shared notation, bibliography, package, test, or thesis source.

## Rules

- Preserve the public/internal boundary and existing document structure.
- Reuse `docs/typst/shared` before introducing recurring notation or terms.
- Resolve citations through `docs/references.bib`; apply the direct-source
  claim checklist and calibrate advisor-facing wording before publication.
- Keep reproducible figure source, frame/units/view metadata, and provenance.
- Keep `.mmd` as source, use the curated symbol map, lint locally, and render
  locally when `mmdc` is available.
- Compile the narrowest owning document and inspect affected pages for math,
  figures, tables, captions, references, and layout.

Complete when the owning source is updated, required local checks pass, and
render evidence or an exact environment blocker is recorded.
