---
name: typst-authoring
description: Use for ARIA-NBV Typst proposal/thesis authoring, shared notation, scientific prose, citations, scientific/geometric figures, tables, Mermaid inclusion, and compile/render QA.
metadata:
  mode: implementation
  not_when:
    - "pure Quarto navigation/frontmatter without Typst or thesis scientific-writing concerns"
    - "a systemic, CI-specific, or persistent docs build failure owns the task"
    - "a broad advisor-facing thesis-scope decision is unresolved"
  handoff_to:
    - "nearest docs guide for public Quarto navigation or docs-boundary edits"
    - "nearest build owner for systemic failures or suspicious rendered output that persists after the Typst loop"
    - "aria-grill for ambiguous advisor-facing research-contract decisions"
  evidence_required:
    - "nearest docs guidance and target Typst imports"
    - "shared notation/glossary check for new symbols, equations, or durable terms"
    - "claim/citation check for advisor-facing literature or thesis claims"
    - "source artifact plus frame, units, projection/view, and provenance for scientific or geometric figures"
    - "compile and rendered-page inspection for non-trivial visual/math edits"
  applies_to:
    - "docs/typst/**"
    - ".agents/skills/typst-authoring/**"
  triggers:
    - "Typst"
    - "main.typ"
    - "thesis seed"
    - "thesis Typst"
    - "shared symbols or equations"
    - "scientific prose in thesis/proposal"
    - "scientific illustration"
    - "3D/geometric figure"
  must_read:
    - "AGENTS.md"
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared"
    - "docs/notation.yml"
    - "docs/typst/shared/style.typ"
    - ".agents/skills/typst-authoring/references/thesis-section-contracts.md"
    - ".agents/skills/typst-authoring/references/empirical-reporting-and-reproducibility.md"
    - ".agents/skills/typst-authoring/references/aria-nbv-notation.md"
    - ".agents/skills/typst-authoring/references/figures-tables.md"
    - ".agents/skills/typst-authoring/references/scientific-visualizations.md"
  context7_refs:
    - "/websites/typst_app"
    - "/typst-community/glossarium"
    - "/cetz-package/cetz"
    - "/jollywatt/typst-fletcher"
    - "/touying-typ/touying"
    - "/websites/quarto"
  literature_refs:
    - "docs/references.bib"
    - "docs/literature/sources.jsonl"
    - "quality-driven-rri"
    - "finite-candidate-rl"
  tool_refs:
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__code_index.search_code_advanced"
  verification:
    - "skill quick_validate.py when available for skill edits"
    - "make check-agent-memory when agent guidance changes"
    - "make typst-authoring-contract for thesis-wide authoring hygiene"
    - "focused Typst compile plus PNG render for document edits"
---

# ARIA-NBV Typst + Thesis Authoring

## Use When

- Editing `.typ` proposal, paper, thesis, or slide sources.
- Adding or revising equations, symbols, glossary terms, citations, figures,
  tables, labels, or Mermaid-derived figures.
- Polishing scientific prose into evidence-backed paragraphs.
- Fixing Typst syntax, math attachment, import, citation, figure, table, label, or rendered-page issues.

## Task Modes

- `notation-edit`: update shared modules before document-local use; read notation,
  math-attachment, and migration references.
- `prose-draft` / `prose-polish`: read thesis-writing, section-contract, and
  claim-discipline references; use the nested fragment, shape, or beat writing
  modes only when useful; preserve claim strength and citations.
- `claim-check`: classify advisor-facing literature or thesis claims and use the
  direct-source checklist in `references/claim-citation-discipline.md`.
- `empirical-results`: read the empirical-reporting reference; require a frozen
  analysis contract, uncertainty, fair controls, and immutable provenance.
- `figure-table` / `visual-qa`: read figures/tables and workflow references;
  scientific, geometric, or 3D work also reads `scientific-visualizations.md`
  and the selected renderer/package reference.

## Rules

1. Inspect nearest docs guidance, target imports, adjacent sections,
   bibliography style, labels, thesis-to-code link tier, and `docs/typst/shared/`.
2. Use shared notation, glossary, and equations before inventing local symbols;
   add recurring terms or equations to shared modules first.
3. Keep notation policy, math-attachment details, claim discipline, figure/table
   conventions, and package notes in the referenced files, not this hot path.
4. Classify advisor-facing claims and complete the direct-source evidence check
   when evidence matters.
5. Use Glossarium-native `@term` / `@term:short` references for durable terms.
6. Write final thesis/proposal prose as paragraphs unless the template asks for lists.
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
   `docs/typst/shared/style.typ`: use `#gh` for final-worthy pinned
   anchors and `#gh-wip` / `#gh-symbol` for removable drafting aids.
4. For thesis, slides, or diagrams that introduce or reuse symbols/equations,
   read `references/aria-nbv-notation.md`; for package-backed layouts or
   slide templates, also read `references/packages/index.md` and
   `references/slides.md` as relevant.
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
