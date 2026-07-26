---
name: aria-docs
description: Author and render ARIA-NBV docs.
metadata:
  mode: implementation
  not_when:
    - "the task is primarily a scientific decision or package implementation"
  handoff_to:
    - "plan-grill for unresolved scientific or advisor-facing decisions"
  evidence_required:
    - "target document, its imports or navigation owner, and adjacent content"
    - "successful focused render plus inspection of affected pages"
  applies_to:
    - "docs/**"
    - "tools/mermaid/**"
  triggers:
    - "Quarto or Typst authoring"
    - "slides, figures, tables, or Mermaid"
  must_read:
    - "docs/AGENTS.md"
    - ".agents/skills/aria-docs/references/workflow.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared"
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
| Thesis prose or structure | target include from `docs/typst/thesis/main.typ` |
| Typst paper or slides | target entrypoint, imports, and adjacent source |
| Shared term, symbol, or equation | existing owner under `docs/typst/shared` |
| Figure, table, or caption | owning source/data plus the including document |
| Mermaid source or export | `references/mermaid.md` |

Follow `references/workflow.md` for authoring, rendering, and visual QA. This
skill routes workflow only; the listed document, notation, package, and thesis
sources own their content.
