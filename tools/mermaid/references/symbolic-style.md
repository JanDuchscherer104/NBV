# Symbolic architecture profile

## Visual baseline and limits

Use the seminar `semidense_frustum`, `pose_encoder`, `global_pool`, `scene_field`
and `head_paper` families for their **visual grammar**: short titles, recognizable
operations, data symbols and informative tensor edges. Read their implementations
before reusing any parameter count, shape or equation. Do not copy historical
notation, make every word a KaTeX expression, or import old model assumptions.
The PR190 examples here are review candidates, not active thesis figures.

Use a real HTML header: `<b>Physical projection</b><br/>$$...$$`. Ordinary text
uses CMU Serif; mathematical content uses the renderer's math font. Do not apply
a global font-weight to all math, because boldness can distinguish scalars,
vectors and matrices. CSS font-family does not install a font. Check regular
and bold faces (`fc-match 'CMU Serif'`, `fc-match 'CMU Serif:style=Bold'`) and the
browser's actual platform font. Never commit/distribute system font files.

## Size the page, not an abstract canvas

Start at **160 mm** width, body/math 24 px, headers 28 px/700, edge labels 22 px,
node gap 18 px, rank gap 30 px and padding 12 px. These are starting points;
choose dimensions from the final-size render. For SVG width W and label size f:

`effective_pt = f * (width_mm * 72 / 25.4) / W`.

Target 10–12 pt body and 12–14 pt titles at final size. The automatic floor is
9 pt body, 11 pt titles and 8 pt labelled edges; the figure must fit 230 mm
height. These editorial thresholds are configurable inspection policy, not
universal readability constants. Inspect at actual scale, not only zoomed in.

Prefer a compact two-column arrangement to a long one-line equation or a
panoramic pipeline. Break long titles semantically, shorten notation by using
its canonical symbol, or split an overloaded view. Do not fill every spare
pixel: gaps make branching, ownership and reading order visible. Node-area
occupancy is only a diagnostic, never an optimization target. Increasing PNG
resolution does not repair undersized type.

## Symbol contracts

`docs/typst/shared` owns meanings and the registered TeX strings;
`docs/notation.yml` is the generated adapter. Check both. The old manual
`aria_symbol_map.yaml` is historical and must not override either owner.

Bind every math block to a whole registered expression on the immediately
following non-comment statement:

```mermaid
%% aria-math: symbols.rl.budget symbols.rl.requested_horizon
Budget["<b>Budget / horizon</b><br/>$$b_t$$ · $$h$$"]
```

Add `%% aria-notation: strict` to the figure. Bind edge-label math the same way.
The checker requires exact TeX, rejects unknown keys, modified indices, extra
expressions, unbound blocks and unused bindings. It does not accept “the symbol
occurs somewhere in the file” as validation. Source lines containing math must
be self-contained. New equations or reusable symbols are registered in Typst
first and generated with the owner workflow. There is no unreviewed local-TeX
escape hatch. A transformation may have a short ordinary-language name when no
registered operator is available; do not fabricate a mathematical operator.

Exact spelling is **not** scientific correctness: frame direction, units,
conditioning, information boundaries, dimensions and epistemic status still
require review. A stale generated projection must be repaired at its owner.

## Topology and semantics

Preserve input green, compute purple, data grey, output red, with dark text and
the existing class definitions. Label inferred/proposed modules and use dashed
borders; label dotted edges by their actual meaning. An enclosure must express
membership, not decorate the picture. Never draw alternatives as simultaneous
inputs. Never draw candidate-conditioned features feeding back into shared scene
memory unless an actual update is intended. A hard action mask is not an input
to a mask-independent scorer; a label mask is not action feasibility.

Only show tensor dtypes/shapes in an implementation-facing view, verified against
source. Use symbols and mathematical domains in conceptual views. Do not replace
specific library contracts with invented shapes merely to look more mathematical.

## Renderer evidence

Official Mermaid math documentation states that default math is browser MathML;
`forceLegacyMathML` requires matching KaTeX CSS supplied by the host. Do not turn
it on without that stylesheet. Mixed HTML titles and math must be tested with
the chosen engine. Root `htmlLabels` is the modern option; duplicated nested
settings are unnecessary in the new profile.

References: https://mermaid.js.org/config/math.html and
https://mermaid.js.org/config/schema-docs/config.html (checked 2026-09-06).

A Mermaid SVG may contain HTML/MathML `foreignObject` elements. Browser rendering
does not prove Typst can consume it. Use a verified browser PDF/PNG export or a
Typst-native realization and inspect the actual final PDF. Keep editable text
and source; do not mistake a foreignObject SVG for a portable all-vector asset.
