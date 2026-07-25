# ARIA Docs Workflow

Use one branch and read only the files it names. Start from the target document
and its imports; use outlines to localize large sources before opening them.

## Quarto

Read `docs/AGENTS.md`, the target page, and its navigation owner. Use
`scripts/nbv_qmd_outline.sh --compact` to localize broad pages. Run
`make qmd-frontmatter-check`; render the touched page or site when layout,
cross-references, execution, or navigation changes.

## Typst, Notation, And Glossary

Read `references/typst.md`. Use:

```bash
make context-typst-outline \
  TYPST_OUTLINE_ARGS='--paper docs/typst/thesis/main.typ --mode outline'
make context-typst-includes \
  TYPST_INCLUDES_ARGS='--paper docs/typst/thesis/main.typ --mode includes'
```

Inspect the target imports and `docs/typst/shared` before changing recurring
terms, symbols, equations, or document-wide style.

## Thesis Or Proposal Prose

Read `references/thesis-writing.md`, the target section, and adjacent sections.
Use `.agents/references/direct_source_claim_checklist.md` for advisor-facing
claims and `.agents/references/thesis_code_links.md` for implementation links.

## Citations And Scientific Figures

Resolve bibliography keys in `docs/references.bib`. For an advisor-facing
claim, inspect an authoritative TeX section, local PDF page, or upstream source
and retain an exact locator. Follow
`.agents/references/direct_source_claim_checklist.md`, calibrate wording, and
record touched-surface render evidence. Figures retain reproducible source plus
units, coordinate frame, fixed view/projection, export settings, and provenance.
Read `references/visuals.md` for figures, tables, captions, and slides.

## Mermaid

Read `references/mermaid.md`. It routes to the symbol map, style guide,
templates, linter, and local renderer without loading unrelated Typst guidance.

## Completion

Run the narrowest owning compile or render. For non-trivial prose, equations,
figures, tables, or slides, export the affected pages to PNG and inspect them.
Report exact commands, outputs, warnings, and any skipped check.
