---
name: aria-nbv-mermaid
description: Use for creating, editing, validating, or rendering ARIA-NBV Mermaid `.mmd` thesis diagrams and diagram templates.
metadata:
  mode: implementation
  not_when:
    - "the task is only Typst layout/prose without Mermaid sources"
    - "a concrete Mermaid parser traceback owns the task"
    - "the requested visual is better as a raster image or non-Mermaid asset"
  handoff_to:
    - "typst-authoring for Typst inclusion, captions, and final page QA"
    - "docs-curator for Quarto pages containing Mermaid fences"
    - "diagnose-aria for concrete Mermaid CLI/render failures"
  evidence_required:
    - "relevant docs/typst/shared symbols or equations before writing math labels"
    - "tools/mermaid symbol map and style guide for thesis figures"
    - "local Mermaid lint before committing .mmd edits"
  applies_to:
    - "**/*.mmd"
    - "tools/mermaid/**"
    - "docs/figures/**"
    - "docs/typst/**/figures/**"
  triggers:
    - "Mermaid"
    - ".mmd"
    - "thesis diagram"
    - "flowchart"
    - "sequence diagram"
  must_read:
    - "AGENTS.md"
    - "docs/AGENTS.md"
    - "tools/mermaid/references/aria_mermaid_style.md"
    - "tools/mermaid/references/aria_symbol_map.yaml"
  canonical_sources:
    - "docs/AGENTS.md"
    - "tools/mermaid/references/aria_mermaid_style.md"
    - "tools/mermaid/references/aria_symbol_map.yaml"
    - "tools/mermaid/scripts/aria_mermaid_lint.py"
    - "docs/typst/shared"
  context7_refs:
    - "/mermaid-js/mermaid"
    - "/websites/typst_app"
  literature_refs:
    - "docs/references.bib"
    - "docs/contents/literature/index.qmd"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
  verification:
    - "python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>"
    - "tools/mermaid/scripts/render_mermaid.sh <file.mmd> <out.svg> when global mmdc is available"
---

# ARIA-NBV Mermaid Figure Skill

Create and maintain Mermaid diagrams for ARIA-NBV thesis and docs surfaces.
The goal is stable, versioned diagrams whose visual grammar and math notation
match `docs/typst/shared`.

## Use When

- Creating or editing `.mmd` files.
- Translating ARIA-NBV architecture, VIN/NBV/RRI/oracle/entity pipelines,
  rollout protocols, storage layouts, or app sequences into Mermaid.
- Validating or exporting thesis diagrams before Typst/Quarto inclusion.
- Updating Mermaid templates, style rules, examples, or the symbol map.

## Rules

1. Read relevant Typst symbols/equations before writing math labels.
2. Use `tools/mermaid/references/aria_symbol_map.yaml` as the curated
   Mermaid/KaTeX projection of shared Typst notation.
3. Start from `tools/mermaid/templates/flowchart_scientific.mmd` or
   `tools/mermaid/templates/sequence_scientific.mmd` unless another Mermaid
   grammar is clearly required.
4. Use the four semantic classes for thesis flowcharts: `input`, `compute`,
   `data`, and `output`.
5. For math-heavy flowcharts, use frontmatter with `htmlLabels: true`,
   `layout: elk`, and the shared class palette.
6. Prefer compact KaTeX labels with a bold title plus one to three math/code
   lines. Use `\begin{array}{c}` for multiline math labels.
7. Do not invent notation inside Mermaid. Add missing notation to Typst shared
   sources first, then update the curated symbol map.
8. Keep `.mmd` as source. Render locally for review; never use online renderers
   for unpublished thesis figures unless the user explicitly permits it.
9. Do not rewrite existing diagrams merely because the linter reports warnings;
   preserve visual intent and migrate only requested or clear mismatches.

## Workflow

1. Determine diagram intent: data flow, model branch, training pipeline,
   rollout protocol, storage layout, sequence, or configuration graph.
2. Read the relevant shared symbols/equations and the Mermaid style guide.
3. Create or edit the `.mmd` from a template or matching example.
4. Run `python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>`.
5. If global `mmdc` is available, run
   `tools/mermaid/scripts/render_mermaid.sh <file.mmd> /tmp/<name>.svg`.
6. If the diagram will enter Typst, hand off to `typst-authoring` for inclusion,
   caption quality, and rendered-page inspection.

## References

- `tools/mermaid/references/aria_mermaid_style.md` - visual grammar.
- `tools/mermaid/references/aria_symbol_map.yaml` - curated notation map.
- `tools/mermaid/templates/` - starting templates.
- `tools/mermaid/examples/` - style anchors and migration examples.
- `tools/mermaid/scripts/` - linter, render wrapper, symbol-map helper.

## Completion

Report the `.mmd` path, lint command and result, render command/result if run,
and any remaining warnings or skipped rendering reason.
