---
name: typst-authoring
description: Use for ARIA-NBV Typst proposal/thesis authoring, shared notation, scientific prose, citations, figures/tables, Mermaid inclusion, and compile/render QA.
metadata:
  mode: implementation
  not_when:
    - "pure Quarto navigation/frontmatter without Typst or thesis scientific-writing concerns"
    - "a systemic, CI-specific, or persistent docs build failure owns the task"
    - "a broad advisor-facing thesis-scope decision is unresolved"
  handoff_to:
    - "docs-curator for public Quarto navigation or docs-boundary edits"
    - "diagnose-aria for systemic build failures or suspicious rendered output that persists after the Typst loop"
    - "plan-grill for ambiguous advisor-facing research-contract decisions"
  evidence_required:
    - "nearest docs guidance and target Typst imports"
    - "shared notation/glossary check for new symbols, equations, or durable terms"
    - "claim/citation check for advisor-facing literature or thesis claims"
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
  must_read:
    - "AGENTS.md"
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md"
  canonical_sources:
    - "docs/AGENTS.md"
    - ".agents/references/source_order.md#role-split"
    - "docs/typst/thesis/main.typ"
    - "docs/typst/shared"
    - ".agents/skills/typst-authoring/references/thesis-section-contracts.md"
    - ".agents/skills/typst-authoring/references/aria-nbv-notation.md"
  context7_refs:
    - "/websites/typst_app"
    - "/websites/quarto"
  literature_refs:
    - "docs/references.bib"
    - "docs/literature/sources.jsonl"
    - "quality-driven-rri"
    - "finite-candidate-rl"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
  verification:
    - "skill quick_validate.py when available for skill edits"
    - "make check-agent-memory when agent guidance changes"
    - "focused Typst compile plus PNG render for document edits"
---

# ARIA-NBV Typst + Thesis Authoring

This is the repo-local guardrail for ARIA-NBV proposal and thesis writing in
Typst. Treat Typst correctness, shared notation, scientific prose, citations,
figures, tables, Mermaid inclusion, and visual QA as one workflow.

## Use When

- Editing `.typ` proposal, paper, thesis, or slide sources.
- Adding or revising equations, symbols, glossary-backed terms, citations,
  figures, tables, captions, labels, or Mermaid-derived figures.
- Polishing advisor-facing thesis prose into evidence-backed paragraphs.
- Updating this skill's fixtures, references, or helper scripts.
- Fixing ordinary Typst syntax, math attachment, import, citation, figure,
  table, label, or rendered-page issues.

## Do Not Use When

- The task is only Quarto navigation/frontmatter; use `docs-curator`.
- A failure is systemic, CI-specific, multi-surface, or persists after the
  compile/render loop; use `diagnose-aria`.
- The research contract or thesis scope is still ambiguous; use `plan-grill`.

## Task Modes

- `notation-edit`: update shared modules before document-local use; read
  notation, math-attachment, and migration references.
- `prose-draft` / `prose-polish`: read thesis-writing, section-contract, and
  claim-discipline references; preserve claim strength and citations.
- `claim-check`: classify claims and run `make kg-claim-check KG_CLAIM='...'`
  for advisor-facing literature or thesis claims.
- `figure-table` / `visual-qa`: read figures/tables and workflow references,
  render locally, inspect pages, and report skipped checks.

## Rules

1. Inspect nearest docs guidance, target imports, adjacent sections,
   bibliography style, labels, and `docs/typst/shared/`.
2. Use shared notation, glossary, and equations before inventing local symbols;
   add recurring terms or equations to shared modules first.
3. Keep notation policy, math-attachment details, claim discipline, figure/table
   conventions, and package notes in the referenced files, not this hot path.
4. Classify advisor-facing claims and run KG claim checks when evidence matters.
5. Use Glossarium-native `@term` / `@term:short` references for durable terms.
6. Write final thesis/proposal prose as paragraphs unless the template asks for
   lists.
7. Compile and inspect rendered pages for equations, figures, tables, captions,
   layout changes, and multi-paragraph thesis prose.

## Workflow

1. Choose the task mode and read only its required references.
2. If notation changes, check `docs/typst/shared` and update the shared module
   before using the symbol in thesis text.
3. For thesis, slides, or diagrams that introduce or reuse symbols/equations,
   read `references/aria-nbv-notation.md`; for package-backed layouts or
   slide templates, also read `references/packages/index.md` and
   `references/slides.md` as relevant.
4. If prose changes, draft claims/evidence first, then convert to paragraphs.
5. If figures or Mermaid assets change, render them locally before inclusion.
6. Compile the document or fixture, render affected pages to PNG, inspect
   visually, then fix and repeat.
7. Report exact compile/render/check commands and any skipped checks.

## References And Commands

Read only the reference needed for the task: notation, math attachments,
notation migration, thesis writing, section contracts, claim/citation
discipline, figures/tables, workflow, external research, data loading, scripting,
layout, Typst symbols, packages, or slides.

Primary checks are `make check-agent-memory` for skill/guidance edits,
`make thesis-pdf` or focused `typst compile ... --root .` for document edits,
and the local render/hygiene scripts when visual QA is required.
