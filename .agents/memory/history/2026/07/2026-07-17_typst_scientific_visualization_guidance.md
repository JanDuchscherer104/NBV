---
id: 2026-07-17_typst_scientific_visualization_guidance
date: 2026-07-17
title: "Typst Scientific Visualization Guidance"
status: done
topics: [typst, thesis, scientific-visualization, skills]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/typst-authoring/SKILL.md
  - .agents/skills/typst-authoring/references/scientific-visualizations.md
  - .agents/skills/typst-authoring/references/figures-tables.md
  - .agents/skills/typst-authoring/references/packages/cetz.md
---

## Task

Extend `typst-authoring` with predictable routing and progressively disclosed
reference guidance for scientific, geometric, spatial, and 3D figures.

## Method And Findings

Kept the skill hot path at 143 lines and placed renderer selection, figure
admissibility, geometric truth, spherical-domain practice, reproducibility,
accessibility, and source quality in one new reference. Existing references
retain ownership of captions/tables/Mermaid and CeTZ-specific setup. The update
adds no package, thesis prose, rendered asset, or Python behavior.

The source set uses official or upstream Typst, CeTZ, Plotly, Rerun,
Matplotlib, and W3C documentation, plus Nature and peer-reviewed PLOS practice
guidance. All referenced URLs returned HTTP 200 on 2026-07-17.

## Verification

- `quick_validate.py .agents/skills/typst-authoring`: passed.
- `make scaffold-audit`: 0 errors and 18 repository-wide warnings; the
  `typst-authoring` warning points to an unchanged existing sentence.
- bounded external-link GET check: all 20 unique URLs returned HTTP 200.
- `make check-agent-memory`: passed.
- `git diff --check`: passed.

## Canonical State Impact

The new scientific-visualization reference is the canonical workflow owner for
future Typst figure routing and QA. Thesis theory, renderer implementation, and
package dependencies are unchanged.
