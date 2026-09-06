---
name: aria-nbv-mermaid
description: Build ARIA-NBV symbol-first diagrams with canonical Typst/LaTeX data notation, source-bound mathematical or computational process bodies, and rendered scientific/reader validation.
---

# ARIA-NBV Mermaid Figures

Teach one mechanism through its data and transformations. A short heading only
names a box; it does not describe its computation. In architecture diagrams,
**data and modalities use canonical symbols; processes show equations, operators,
layer pipelines or compact computational pseudocode**. Prose belongs mainly in
the caption. Do not satisfy this requirement by adding a few symbols to an
otherwise prose-only graph.

## Owner-first route

Read root/nearest `AGENTS.md`, the exact passage and its implementation. Preserve
one scientific abstraction level and the distinction between selected methods,
privileged controls and proposed architectures.

- Meanings and executable Typst: `docs/typst/shared/symbols.typ`,
  `equations.typ`, and their domain modules in `symbols/` and `equations/`.
- Generated LaTeX: `docs/notation.yml`, `symbols.<domain>.<key>.tex` and
  `equations.<domain>.<key>.tex`. It is an adapter, never a competing owner.
- RL/history/value/replay: `symbols/rl.typ`, `equations/rl.typ`.
- Candidate encoding, attention, fusion: `symbols/model.typ`, `equations/model.typ`.
- Scene modalities, EVL, rays, pooling: `symbols/scene.typ`, `equations/scene.typ`.
- Targets, observations, cameras, transforms and shapes: `symbols/{entity,obs,
  oracle,spatial,frame,shape,vin}.typ` and the corresponding equation owner.

Copy the current generated TeX only after checking meaning and transform direction
in Typst. Register missing reusable notation through `typst-authoring`, then
regenerate; never edit `notation.yml` or the old manual Mermaid symbol map.
For a pinned PR example, inspect that exact owner/ref and revalidate against the
destination branch before inclusion.

Progressive references:

- [Symbolic/computational style and examples](../../../tools/mermaid/references/symbolic-style.md).
- [Scientific and cold-reader review](references/figure-review.md).
- [Bounded iteration and Mermaid Chart](references/iteration.md).
- Scientific geometry, frusta, plots and final PDF inclusion: `typst-authoring`.

## Non-negotiable authoring contract

1. Start from `tools/mermaid/templates/flowchart_symbolic.mmd`. Keep short bold
   CMU Serif headers outside mathematics and retain the physical-size profile.
2. Require `%% aria-notation: strict` and
   `%% aria-architecture: symbolic-computational` for new architecture figures.
3. Every data/input/output node carries canonical math. Every process carries
   an actual equation or `<code>` computation, not just its name or output symbol.
4. Bind each `$$...$$` block to its exact `%% aria-math:` key. Bind pseudocode
   with `%% aria-compute: equations.<domain>.<key>` to the relevant Typst equation.
   Computational port names are local roles, not new thesis symbols; explain
   their correspondence and check actual layers/operands against implementation.
5. Prefer a compact canonical equation. When that would obscure the mechanism,
   show a source-bound call, aggregation, conditional, or layer pipeline with
   canonical inputs/outputs nearby. Never use a longer prose sentence merely
   because no single registered operator exists.
6. Put transformations or transferred symbolic data on edges where useful.
   Keep control qualifiers short. Do not invent an edge shape, frame transform,
   parameter count or modality for appearance.
7. Use the seven seminar examples listed in the style reference for their
   operations-and-symbols grammar, not their historical notation or model choices.

## Working and verification loop

Freeze incoming reader knowledge, one insight and one likely misconception.
Draft the source, then perform scientific and cold-reader passes. A same-context
pass is self-review, not independent approval. Revise one diagnosed defect at a
time; preserve causality and support instead of adding layout-only dependencies.

```sh
python3 tools/mermaid/scripts/aria_mermaid_lint.py path/to/figure.mmd
python3 tools/mermaid/scripts/aria_mermaid_notation.py --require-strict --require-architecture path/to/figure.mmd
python3 -W error -m unittest discover -s scripts/tests -p test_aria_mermaid_notation.py
tools/mermaid/scripts/render_mermaid.sh path/to/figure.mmd /tmp/figure.svg
node tools/mermaid/scripts/inspect_mermaid.mjs /tmp/figure.svg 160 /tmp/figure
```

Use official Mermaid Chart `display_mermaid` for an interactive preview and
copy edits back to `.mmd`. A successful tool response alone is not validation
or evidence of visual inspection. Local/hosted rendering owns reproducibility.
Check actual fonts, node/code/edge sizes, clipping and grayscale at the intended
width; change wrapping/layout before reducing type. A source reference does not
prove pseudocode correctness, nor does exact spelling prove scientific meaning.

## Completion

Report source/ref, symbolic and computational coverage, notation checks, actual
render/font/size evidence and inspected color/grayscale outputs. Publish only
within user authorization. Final thesis placement requires destination-notation,
caption/include/cross-reference and PDF-page checks through `typst-authoring`.
