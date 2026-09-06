# Symbolic architecture profile

## Visual baseline and limits

Use the seminar `semidense_frustum`, `pose_encoder`, `global_pool`, `scene_field`
and `head_paper` families for their **visual grammar**: short titles, recognizable
operations, data symbols and informative tensor edges. Read their implementations
before reusing any parameter count, shape or equation. Do not copy historical
notation, make every word a KaTeX expression, or import old model assumptions.
The PR190 examples here are review candidates, not active thesis figures.

Use a real HTML header: `<b>Physical projection</b>$$...$$`. Ordinary text
uses CMU Serif; mathematical content uses the renderer's math font. Do not apply
a global font-weight to all math, because boldness can distinguish scalars,
vectors and matrices. CSS font-family does not install a font. Check regular
and bold faces (`fc-match 'CMU Serif'`, `fc-match 'CMU Serif:style=Bold'`) and the
browser's actual platform font. Never commit/distribute system font files.

Mermaid can introduce a flex-row wrapper that discards the intended
header/body line break. The symbolic template uses
`.nodeLabel div { flex-direction: column; }` and makes the bold header a block.
Verify the actual header and formula occupy separate lines; a literal `<br/>`
in source is not proof. Do not add a redundant break after a block header or
multiplication-like dots between separate symbol labels. The browser inspector
rejects math positioned beside or above the title. Inspect the emitted CSS as
well as the source: host-side sanitization can remove theme rules, and a fallback
render is not style parity.

## Size the page, not an abstract canvas

Start at **160 mm** width, body/math 24 px, headers 28 px/700, edge labels 22 px,
node gap 18 px, rank gap 30 px and padding 12 px. These are starting points;
choose dimensions from the final-size render. For SVG width W and label size f:

`effective_pt = f * (width_mm * 72 / 25.4) / W`.

Target 10–12 pt body and 12–14 pt titles at final size. The automatic floor is
9 pt body, 11 pt titles and 8 pt labelled edges; the figure must fit 230 mm
height. These editorial thresholds define this inspection profile, not
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
Budget["<b>Budget / horizon</b>$$b_t$$ $$h$$"]
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

Use `forceLegacyMathML: true` for this symbolic profile so calligraphic,
bold and other mathematical alphabets are rendered by KaTeX HTML/CSS rather
than depending on browser MathML variants. The pinned Mermaid CLI supplies
its installed KaTeX stylesheet and matching web fonts during layout. A host
such as Mermaid Chart or a GitHub fence must also supply matching CSS; do not
assume preview parity. CMU Serif is for titles/body text, not a global override
of mathematical glyph fonts.

The SVG inspector reuses the installed KaTeX CSS and temporarily loads font
bytes in its browser DOM; it never writes or distributes font assets. It
checks actual CMU title fonts, KaTeX math fonts and header/body positions.
Review PNGs are self-contained. Exported SVGs remain browser assets that may
require KaTeX styles; do not promote them as portable final-thesis vectors.

References: https://mermaid.js.org/config/math.html and
https://github.com/mermaid-js/mermaid-cli/blob/11.17.0/src/index.js
(checked 2026-09-06).

A Mermaid SVG may contain HTML/MathML `foreignObject` elements. Browser rendering
does not prove Typst can consume it. Use a verified browser PDF/PNG export or a
Typst-native realization and inspect the actual final PDF. Keep editable text
and source; do not mistake a foreignObject SVG for a portable all-vector asset.
