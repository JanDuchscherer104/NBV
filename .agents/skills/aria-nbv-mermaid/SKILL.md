---
name: aria-nbv-mermaid
description: Create and review ARIA-NBV symbolic architecture diagrams, validate canonical notation, render publication-sized figures, and iterate through professor/student critique with Mermaid Chart previews.
---

# ARIA-NBV Mermaid Figures

Teach one mechanism. Keep `.mmd` as the editable source and `tools/mermaid` as
the rendering/validation owner. Scientific truth belongs to the exact thesis,
implementation, configuration and tests, not to a diagram or a rendering tool.

## Start narrowly

Read root and nearest `AGENTS.md`, then the exact passage or implementation.
For existing diagrams inspect both source and rendered baseline. The seminar
figures in `docs/figures/diagrams/vin_nbv/mermaid/` are visual references, not
current architecture evidence. Prefer short headers, symbolic data, named
transformations and purposeful edge labels over paragraphs in boxes.

Load only the relevant branch:

- **Style and authoring:** [symbolic-style.md](../../../tools/mermaid/references/symbolic-style.md).
- **Scientific and reader review:** [figure-review.md](references/figure-review.md).
- **Iterative research and plugin use:** [iteration.md](references/iteration.md).
- **Notation changes or final thesis inclusion:** `typst-authoring`; inspect
  `docs/typst/shared/symbols.typ`, `equations.typ` and their domain modules.
- **Metric geometry, frusta or quantitative plots:** hand off to `typst-authoring`.
  A topology flowchart cannot certify physical geometry.

## Working loop

1. State the incoming reader knowledge, one takeaway, likely misconception and
   exact source. Decide retain, revise, replace or remove; do not improve an
   obsolete diagram merely because it exists.
2. Select one abstraction level: conceptual relation, selected architecture or
   implementation tensor flow. Separate target architectures from current
   controls. Freeze the applicable source/notation revision.
3. Start from `tools/mermaid/templates/flowchart_symbolic.mmd`. Titles are bold
   **CMU Serif text**, outside math. Put only canonical symbols/equations in
   `$$...$$`; use an adjacent `%% aria-math:` binding for every block.
4. Check spelling against the generated `docs/notation.yml`, after checking
   meaning in the Typst owner. Never edit the generated YAML or revive the
   handwritten `aria_symbol_map.yaml` as another authority.
5. Use the official Mermaid Chart `display_mermaid` action for an interactive
   preview. It returns source to a browser widget; a successful tool response
   alone is **not** syntax, rendering, font or visual-inspection evidence.
6. Run local/hosted validation below. Inspect the actual result at its intended
   width and in grayscale. Change topology, line breaks, padding and spacing
   before shrinking type. Do not add false dependencies just to force layout.
7. Perform distinct scientific and cold-reader passes; revise one diagnosed
   defect at a time. Do not call a same-context pass an independent review.
8. Publish only within the user's authorization. Final thesis placement requires
   caption, include, cross-reference and PDF QA through `typst-authoring`.

## Proof

```sh
python3 tools/mermaid/scripts/aria_mermaid_lint.py path/to/figure.mmd
python3 tools/mermaid/scripts/aria_mermaid_notation.py --require-strict path/to/figure.mmd
python3 -W error -m unittest discover -s scripts/tests -p test_aria_mermaid_notation.py
tools/mermaid/scripts/render_mermaid.sh path/to/figure.mmd /tmp/figure.svg
node tools/mermaid/scripts/inspect_mermaid.mjs /tmp/figure.svg 160 /tmp/figure
```

The inspector uses the existing local CLI's Puppeteer dependency. No second
renderer is introduced. Missing CLI, fonts, browser or exact-source access is a
named gap; use hosted CI when available, never a hand-drawn substitute as proof.
For branch-specific examples pass `--notation` with that branch's verified
projection. Revalidate against the destination branch before promotion.

## Completion

Report source/ref, scientific corrections, exact-label test result, renderer
version, font evidence, physical width and effective type sizes, inspected
color/grayscale artifacts and remaining integration limits. A syntax check,
prototype widget or source-only PR must not be called a publication-ready figure.
