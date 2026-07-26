---
name: aria-docs
description: Author and render ARIA-NBV docs.
metadata:
  mode: implementation
  not_when:
    - "the task is primarily a scientific decision or package implementation"
    - "Python API docstrings are the primary output"
  handoff_to:
    - "plan-grill for unresolved scientific or advisor-facing decisions"
    - "python-docstrings for Python API documentation"
  evidence_required:
    - "target document, its imports or navigation owner, and adjacent content"
    - "shared notation and glossary owners for durable terms, symbols, or equations"
    - "direct-source evidence and an exact locator for research claims"
    - "reproducible source and provenance for scientific figures or tables"
    - "successful focused render plus inspection of affected pages"
  applies_to:
    - "docs/**"
    - "tools/mermaid/**"
  triggers:
    - "Quarto or Typst authoring"
    - "thesis prose, claims, citations, notation, or equations"
    - "slides, scientific figures, tables, or Mermaid"
  must_read:
    - "docs/AGENTS.md"
    - ".agents/skills/aria-docs/references/workflow.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared"
    - "docs/references.bib"
    - ".agents/references/direct_source_claim_checklist.md"
    - ".agents/references/thesis_code_links.md"
    - ".agents/skills/aria-docs/references/notation-and-math.md"
    - ".agents/skills/aria-docs/references/writing-and-claims.md"
    - ".agents/skills/aria-docs/references/figures-and-tables.md"
    - ".agents/skills/aria-docs/references/typst-toolkit.md"
    - "tools/mermaid/references/aria_mermaid_style.md"
    - "tools/mermaid/references/aria_symbol_map.yaml"
  verification:
    - "focused Quarto or Typst render and affected-page inspection"
    - "python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd> for Mermaid"
---

# ARIA Docs

Choose one branch and open only its exact owners:

| Task | Owner path |
| --- | --- |
| Quarto page or navigation | target `.qmd` and `docs/AGENTS.md` |
| Thesis prose, claim, citation, or structure | `references/writing-and-claims.md` |
| Shared term, symbol, equation, or math syntax | `references/notation-and-math.md` |
| Figure, table, caption, or scientific visual | `references/figures-and-tables.md` |
| Typst package, data, layout, scripting, or slides | `references/typst-toolkit.md` |
| Mermaid source or export | `references/mermaid.md` |

Follow `references/workflow.md` for authoring, rendering, and visual QA. This
skill routes workflow only; the listed document, notation, package, and thesis
sources own their content.
