---
name: typst-authoring
description: Use only when the current task executes accepted-content Typst realization, notation, figures, tables, citations, compilation, rendering, or release work; do not load for handoffs addressed to typst-authoring or technical/generated Typst data-consumer schema inspection.
---

# Typst Authoring

Activate only for accepted-content Typst execution. A handoff names its
destination and payload without loading this skill; technical or generated
Typst data-consumer schema inspection stays with the producer owner.

Own the accepted-content surface: express agreed scientific content in Typst,
preserve shared notation and local style, and prove the build and release
state. Do not construct arguments or synthesize literature; route those tasks
to `academic-writing`. Do not decide whether a claim is scientifically
supported; route that question to `scientific-review`.

## Workflow

1. Read the nearest `AGENTS.md`, identify the exact Typst owner, and inspect
   adjacent imports, shared notation, labels, and bibliography usage.
2. Select the smallest branch reference:
   - notation or equation attachment: [`aria-nbv-notation.md`](references/aria-nbv-notation.md),
     [`math-attachments.md`](references/math-attachments.md), and
     [`notation-migration.md`](references/notation-migration.md);
   - figures, tables, or visual QA: [`figures-tables.md`](references/figures-tables.md)
     and, for scientific or geometric work,
     [`scientific-visualizations.md`](references/scientific-visualizations.md);
   - Typst syntax, symbols, or data structures: use the narrowest of
     [`typst-essentials.md`](references/typst-essentials.md),
     [`typst-symbols.md`](references/typst-symbols.md),
     [`typst-data-structures.md`](references/typst-data-structures.md), or
     [`typst-docs-notes.md`](references/typst-docs-notes.md);
   - data, scripting, or layout: [`data-loading.md`](references/data-loading.md),
     [`scripting.md`](references/scripting.md), or [`layout.md`](references/layout.md);
   - slides or package-backed content: read [`slides.md`](references/slides.md)
     or [`packages/index.md`](references/packages/index.md) only when that
     surface is present, then the selected package leaf;
   - prose, claim, or citation handoff: [`claim-citation-discipline.md`](references/claim-citation-discipline.md);
   - accepted empirical results or report-backed content:
     [`empirical-reporting-and-reproducibility.md`](references/empirical-reporting-and-reproducibility.md);
   - compile, render, or release QA: [`workflow.md`](references/workflow.md).
3. Make the smallest source edit. Shared notation, glossary terms, equations,
   and active thesis content stay with their existing exact owners.
4. Compile and inspect affected output when layout or meaning can change. Run
   the owner-defined authoring contract and report skipped proof.

## Current API handoff

When current Typst API or package behavior is genuinely uncertain, inspect
local owners first, then use the Context7 plugin route described by the single
[Context7 registry owner](../aria-nbv-context/references/context7_library_ids.md).
This is a decision-point lookup, not a replacement for repository sources. Use
[`external-research.md`](references/external-research.md) only for its narrow
current-API query guidance.

## Completion

The handoff is complete when accepted content is present in the exact Typst
owner, relevant compile/render or hygiene proof is fresh, and scientific
uncertainty is handed to review rather than silently resolved during
realization.
