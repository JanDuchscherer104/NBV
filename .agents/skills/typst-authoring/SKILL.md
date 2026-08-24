---
name: typst-authoring
description: Use for Typst source edits or accepted-content realization, including notation, equations, figures, tables, citations, source links, compilation, rendering, or page QA; hand off argument construction and independent review.
---

# Typst Authoring

Own accepted-content realization: express agreed scientific content in Typst,
preserve shared notation and local style, and prove the rendered result. For
argument construction use `academic-writing`; for independent claim validity
use `scientific-review`.

## Workflow

1. Read the nearest docs guide, identify the exact Typst owner, and inspect
   adjacent imports, shared notation, labels, and bibliography use.
2. For every non-trivial meaning- or layout-affecting edit, read
   [`workflow.md`](references/workflow.md). Load only the additional branch
   required by the change:
   - notation or equation attachment: [`aria-nbv-notation.md`](references/aria-nbv-notation.md),
     [`math-attachments.md`](references/math-attachments.md), or
     [`notation-migration.md`](references/notation-migration.md);
   - figures, tables, or visual QA: [`figures-tables.md`](references/figures-tables.md)
     and, when scientific or geometric, [`scientific-visualizations.md`](references/scientific-visualizations.md);
   - Typst syntax, symbols, data, scripting, or layout: the narrowest matching
     reference among [`typst-essentials.md`](references/typst-essentials.md),
     [`typst-symbols.md`](references/typst-symbols.md),
     [`typst-data-structures.md`](references/typst-data-structures.md),
     [`typst-docs-notes.md`](references/typst-docs-notes.md),
     [`data-loading.md`](references/data-loading.md),
     [`scripting.md`](references/scripting.md), and [`layout.md`](references/layout.md);
   - slides or package-backed content: [`slides.md`](references/slides.md) or
     [`packages/index.md`](references/packages/index.md), then only its needed leaf;
   - code-reference anchors or draft/final link behavior:
     [`style.typ`](../../../docs/typst/shared/style.typ);
   - accepted claim/citation realization: the academic-writing
     [`claim-citation discipline`](../academic-writing/references/claim-citation-discipline.md),
     or empirical-result realization:
     [`empirical-reporting-and-reproducibility.md`](../scientific-review/references/empirical-reporting-and-reproducibility.md).
3. Make the smallest source edit. Shared notation, glossary terms, equations,
   bibliography identities, and active thesis content remain with their exact
   owners.
4. Compile and inspect affected output when layout or meaning can change. Run
   the owner-defined authoring contract and report any skipped proof.

For current Typst or package API uncertainty, inspect local owners first, then
read [`external-research.md`](references/external-research.md) and use the
conditional Context7 route in `aria-nbv-context`.

## Completion

Accepted content is present in its exact Typst owner, relevant compile/render or
hygiene proof is fresh, and scientific uncertainty is handed to review rather
than silently decided during realization.
