# Symbolic and computational architecture profile

## The seminar baseline

Inspect sources in `docs/figures/diagrams/vin_nbv/mermaid/` before choosing a visual
vocabulary. These seven examples demonstrate what to retain:

| Source | Useful explanatory device |
|---|---|
| `global_pool.mmd` | Pooling calls, projection statistics and an explicit FiLM modulation relation. |
| `head_paper.mmd` | Feature concatenation, reshape, layer pipeline and decoding operations. |
| `pose_encoder.mmd` | Frame transform, pose vector and encoding are distinct transformations. |
| `scene_field.mmd` | Count normalization, derived channels and projection form an actual computation. |
| `semidense_frustum.mmd` | Scatter accumulation, convolution and reduction expose the mechanism. |
| `semidense_proj.mmd` | Projection followed by weighted statistics, with symbolic data on edges. |
| `trajectory.mmd` | Relative-frame conversion, temporal encoding and attention have separate roles. |

Retain this grammar, not historical symbols, layer counts, parameter totals or
claims. Do not put the whole diagram inside KaTeX merely to get a serif face.
The current PR190 sources are review candidates, not active thesis includes.

## Show the operation, not just the noun

Bad: a purple box containing only **A1 attention**, **Feature fusion**, or a lone
output token. Better: a short header, a computational body such as
`CrossAttn(query, key=state, value=state)` or
`concat(query, context, query * context)`, and canonical input/output symbols.
Likewise, **Replay step** should expose pose/prefix/budget updates; **Spatial
pooling** should expose the target, frustum and intersection reductions.

Use a canonical equation directly when compact:

```mermaid
%% aria-math: equations.rl.qh_representation_map
Map["<b>State construction</b>$$z_t^{\sigma}=\phi_{\sigma}(\mathcal{H}_t)$$"]:::compute
```

When a full equation is too wide, use an explicitly source-bound computational
abstraction rather than inventing LaTeX or a new project symbol:

```mermaid
%% aria-compute: equations.model.qh_state_fusion_controls
Read["<b>A1 read</b><code>CrossAttn(query,<br/>key=state, value=state)</code>"]:::compute
```

Here `query` is the incoming canonical candidate-row feature; `state` is the
five-token stack in the cited equation. Port names inside code are local
computational roles, not new mathematical notation. Describe their correspondence
in the caption/source note. A library-layer pipeline, e.g. `Linear → GELU →
LayerNorm`, is appropriate only when those layers and their order match the code.
Do not copy the seminar's old layers into the new scorer.

A pseudocode binding proves that an equation owner exists. It does **not** prove
that a hand-written call is equivalent to it. Check operands, order, conditioning,
source access, terminal handling and library details against that owner and its
implementation. Non-executable conceptual operations must be identified as such.

## Canonical notation route

Read `docs/typst/shared/symbols.typ` and `equations.typ`, then the corresponding
`symbols/<domain>.typ` or `equations/<domain>.typ`. These are canonical. They own
RL values and states; model encodings/fusion; scene fields/rays/pooling; target
geometry; observations; candidates; frames; transformations; and tensor shapes.

`docs/notation.yml` is the generated LaTeX adapter. A key such as
`symbols.model.candidate_row` resolves to that record's `tex`; an equation key
such as `equations.model.qh_state_fusion_controls` resolves similarly. Never
hand-edit this adapter or maintain a Mermaid-only symbol dictionary.

Bind every mathematical node or edge block to its complete canonical expression:

```mermaid
%% aria-math: symbols.rl.budget symbols.rl.requested_horizon
Budget["<b>Budget / horizon</b>$$b_t$$ $$h$$"]:::input
```

`aria_mermaid_notation.py` retains exact matching: modified indices, extra terms,
unknown keys, unbound blocks and unused bindings fail. No substring matching,
manual formula allowlist or arbitrary TeX escape hatch is accepted. Register
new reusable expressions in Typst and regenerate before using them.

## Enforced architecture coverage

Add both directives and run `--require-strict --require-architecture`:

```text
%% aria-notation: strict
%% aria-architecture: symbolic-computational
```

The narrow authoring form is one quoted rectangular node per line with an inline
`input`, `data`, `compute` or `output` class. This makes every node auditable.
Data/input/output nodes need canonical mathematics. Compute nodes need an exact
equation or source-bound `<code>` call/pipeline. A symbol alone does not describe
a computation. Body prose, title-only boxes, unowned pseudocode, hidden TeX,
untyped nodes and class-assignment bypasses fail. Code may coexist with a
canonical output symbol; its source binding and math binding remain separate.
Edge mathematics uses the same exact bindings; ordinary control qualifiers are
limited to three words.

At most two `status` nodes may express terminal logical outcomes such as
**Harmful aliasing**. They carry no data or computation and have no outgoing
edges. They are not an exemption for unnamed processes or missing modalities.
The gate checks form and traceability; it does not prove scientific correctness
or replace Mermaid syntax/rendering validation. Legacy figures remain historical
unless deliberately migrated; the new template and PR190 examples must pass.

## Typography and page size

Use real bold CMU Serif HTML titles, with KaTeX for mathematics. Verify installed
regular/bold faces and actual browser glyph fonts; CSS does not install a font.
Never commit or distribute font files. Do not apply boldness indiscriminately
to math, where it distinguishes scalars, vectors and matrices.

Start with 160 mm width, 28 px bold headers, 24 px math, 22 px computational/edge
text, 16 px node gaps, 24 px rank gaps and 12 px padding. These are starting
values, not proof of legibility. For SVG width W and text size f:

`effective_pt = f * (width_mm * 72 / 25.4) / W`.

Aim for 10–12 pt body and 12–14 pt headings at final size. The inspection floors
are 9 pt body **and code**, 11 pt headings and 8 pt edge labels, with height at
most 230 mm. Avoid a panorama, split an overloaded mechanism, or wrap calls at
argument boundaries before shrinking text. Occupancy is diagnostic, never a
reason to erase scientifically meaningful separation. PNG resolution does not
repair small typography.

Mermaid may wrap labels in a flex row. The profile forces label divs to a column
and headers/code to blocks. Check the rendered header, code and formulas rather
than trusting `<br/>`. Do not add redundant breaks or multiplication-like dots
between unrelated symbols. Keep semantic class colors, but encode scientific
boundaries with words, enclosure or stroke as well, so grayscale preserves them.

## Rendering and publication

The pinned CLI supplies KaTeX CSS for `forceLegacyMathML: true`. An interactive
Mermaid Chart/GitHub host may differ. Use the official plugin to preview exact
source, then the repository wrapper and inspector for reproducible rendering.
A successful display tool call is not server validation or visual inspection.
The inspector rehydrates matching KaTeX assets transiently, measures actual code
sizes as well as headings/math, and exports self-contained PNG previews.

Browser SVGs can depend on CSS and `foreignObject`; do not claim portable Typst
vectors. Use a verified export or Typst-native realization and inspect the final
PDF at its actual insertion width. Keep `.mmd` as the editable source.

Renderer references: https://mermaid.js.org/config/math.html and
https://github.com/mermaid-js/mermaid-cli/blob/11.17.0/src/index.js.
