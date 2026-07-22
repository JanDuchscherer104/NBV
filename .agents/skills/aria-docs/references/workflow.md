# ARIA Docs Workflow

Use one branch and read only the files it names.

## Quarto

Read `docs/AGENTS.md`, the target page, and its navigation owner. Use
`scripts/nbv_qmd_outline.sh --compact` to localize broad pages. Run
`make qmd-frontmatter-check`; render the touched page or site when layout,
cross-references, execution, or navigation changes.

## Typst And Thesis Prose

Read `docs/AGENTS.md`, target imports and adjacent sections, then
`docs/typst/shared` for notation or durable terms. Keep final thesis prose in
paragraphs, match claim strength to evidence, and classify implementation links
with `.agents/references/thesis_code_links.md`. Compile the focused document
with `--root .`, render affected pages when needed, and inspect them visually.

## Citations And Scientific Figures

Resolve bibliography keys in `docs/references.bib`. For an advisor-facing
claim, inspect an authoritative TeX section, local PDF page, or upstream source
and retain an exact locator. Follow
`.agents/references/direct_source_claim_checklist.md`, calibrate wording, and
record touched-surface render evidence. Figures retain reproducible source plus
units, coordinate frame, fixed view/projection, export settings, and provenance.

## Mermaid

Read `tools/mermaid/references/aria_mermaid_style.md` and
`tools/mermaid/references/aria_symbol_map.yaml`; inspect shared Typst notation
before math labels. Start from a local template when useful. Run:

```bash
python tools/mermaid/scripts/aria_mermaid_lint.py <file.mmd>
tools/mermaid/scripts/render_mermaid.sh <file.mmd> <out.svg>
```

The render step is conditional on a global `mmdc`. Keep unpublished thesis
figures local and never use an online renderer without explicit permission.
