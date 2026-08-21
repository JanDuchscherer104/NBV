---
name: typst-authoring
description: Use for ARIA-NBV Typst proposal or thesis authoring, shared notation, scientific prose, citations, scientific or geometric figures, tables, Mermaid inclusion, and compile or render QA.
---

# ARIA-NBV Typst + Thesis Authoring

## Use When

- Editing `.typ` proposal, paper, thesis, or slide sources.
- Adding or revising equations, symbols, glossary terms, citations, figures,
  tables, labels, or Mermaid-derived figures.
- Polishing scientific prose into evidence-backed paragraphs.
- Fixing Typst syntax, math attachment, import, citation, figure, table, label, or rendered-page issues.

## Task Modes

- `notation-edit`: update shared modules before document-local use; read
  [`aria-nbv-notation.md`](references/aria-nbv-notation.md),
  [`math-attachments.md`](references/math-attachments.md), and
  [`notation-migration.md`](references/notation-migration.md).
- `prose-draft` / `prose-polish`: read [`thesis-writing.md`](references/thesis-writing.md),
  [`thesis-section-contracts.md`](references/thesis-section-contracts.md), and
  [`claim-citation-discipline.md`](references/claim-citation-discipline.md); use
  the nested fragment, shape, or beat writing modes only when useful; preserve
  claim strength and citations.
- `claim-check`: classify reviewed literature or thesis evidence and use the
  direct-source checklist in [`claim-citation-discipline.md`](references/claim-citation-discipline.md).
- `empirical-results`: read
  [`empirical-reporting-and-reproducibility.md`](references/empirical-reporting-and-reproducibility.md); require a frozen
  analysis contract, uncertainty, fair controls, and immutable provenance.
- `figure-table` / `visual-qa`: read [`figures-tables.md`](references/figures-tables.md)
  and [`workflow.md`](references/workflow.md); scientific, geometric, or 3D
  work also reads [`scientific-visualizations.md`](references/scientific-visualizations.md)
  and the selected renderer/package reference.

## Conditional References

- **Typst language, syntax, symbols, or data structures:** When a construct or
  API is uncertain, read the narrowest of
  [`typst-essentials.md`](references/typst-essentials.md),
  [`typst-symbols.md`](references/typst-symbols.md),
  [`typst-data-structures.md`](references/typst-data-structures.md), or
  [`typst-docs-notes.md`](references/typst-docs-notes.md).
- **Scripting or data loading:** For reusable code, control flow, modules, or
  external tables/configuration, read [`scripting.md`](references/scripting.md)
  or [`data-loading.md`](references/data-loading.md).
- **Layout:** For flow, spacing, columns, grids, transforms, or measurement,
  read [`layout.md`](references/layout.md).
- **External research:** When local references are insufficient or current
  upstream evidence is required, read
  [`external-research.md`](references/external-research.md), then use the
  local-owner and Context7 route above.

For current Typst, package, or API behavior, hand off through
[`aria-nbv-context`](../aria-nbv-context/SKILL.md) and read its
[Context7 registry](../aria-nbv-context/references/context7_library_ids.md)
only after inspecting local owners and installed call sites.

## Rules

1. Inspect nearest docs guidance, target imports, adjacent sections,
  bibliography style, labels, thesis-to-code link tier, and `docs/typst/shared/`.
2. Use shared notation, glossary, and equations before inventing local symbols;
   add recurring terms or equations to shared modules first. Edit
   `docs/typst/shared/glossary.typ` for durable terms; treat
   `docs/typst/glossary/` as rendered/modular output, not the term owner.
3. Keep notation policy, math-attachment details, claim discipline, figure/table
   conventions, and package notes in the referenced files, not this hot path.
4. Classify literature-facing claims and complete the direct-source evidence
   check when evidence matters.
5. Use Glossarium-native `@term` / `@term:short` references for durable terms.
6. Write final thesis/proposal prose as paragraphs unless the template asks for
   lists.
7. Compile and inspect rendered pages for equations, figures, tables, captions,
   layout changes, and multi-paragraph thesis prose.

## Workflow

1. Choose the task mode and read only its required references.
2. If notation changes, check `docs/typst/shared` and update the shared module
   before using the symbol in thesis text.
   The repository contract rejects authored display blocks that bypass
   `#eqs.*`, and checks recurring symbols against the shared facades. Equation
   binders and other local dummy variables remain local; they are not global
   notation obligations.
3. If thesis prose links to implementation code, classify the link with
   [`docs/typst/shared/style.typ`](../../../docs/typst/shared/style.typ): use `#gh` for final-worthy pinned
   anchors and `#gh-wip` / `#gh-symbol` for removable drafting aids.
4. For thesis, slides, or diagrams that introduce or reuse symbols/equations,
   read [`references/aria-nbv-notation.md`](references/aria-nbv-notation.md);
   for package-backed layouts, read
   [`references/packages/index.md`](references/packages/index.md); for slide
   templates, read [`references/slides.md`](references/slides.md).
5. If prose changes, draft claims/evidence first, then convert to paragraphs;
   empirical sentences must resolve scope, evidence, uncertainty, and artifact
   provenance or remain explicitly hypothetical.
6. For scientific figures, choose the renderer by scientific role and preserve
   reproducible source plus fixed view/export metadata; render assets locally.
7. Compile the document or fixture, render affected pages to PNG, inspect
   visually, then fix and repeat.
8. Run `make typst-authoring-contract` for thesis changes. It checks approved
   structural-label prefixes and exact authored-label scope, keeps
   generated/query and fixture labels excluded, and rejects implementation
   keys or status markers in ordinary submission prose. Explicit code spans
   and guarded development material are allowed contexts.
9. Report exact compile/render/check commands and any skipped checks.

## References And Commands

Read only the reference needed for the task: notation, math attachments,
notation migration, thesis writing, section contracts, claim/citation
discipline, figures/tables, workflow, external research, data loading, scripting,
layout, Typst symbols, scientific visualizations, packages, or slides.
Primary checks are `make check-agent-memory` for skill/guidance edits,
`make thesis-pdf` or focused `typst compile ... --root .` for document edits,
and the local render/hygiene scripts when visual QA is required.
