# Mathematical diagrams, owned by Typst

## One source of mathematics

Authored `.mmd` files name the same objects as Typst:

```text
%% aria-notation: typst
%% aria-architecture: symbolic-computational
Mask["<b>Support</b>$$#symb.rl.action_mask$$"]:::input
Policy["<b>Selection</b>$$#eqs.rl.qh_masked_argmax$$"]:::compute
Mask --> Policy
```

The compiler looks up the exact `typst` field in generated `docs/notation.yml`,
substitutes its `tex` projection, and applies the existing exact-math and
architecture checks. Unknown names, missing or corrupt owner fields, free TeX,
suffix edits and pseudocode escape hatches fail. Changing a canonical projection
updates every consumer without editing diagram source. Optional receipts bind
source, adapter and generated output hashes to the actual owner dependencies.

This is a narrow reference syntax, **not a Typst interpreter**. Mermaid Chart
and GitHub receive the generated plain Mermaid. Never publish raw owner syntax
as a supposedly renderable Mermaid fence, or edit the generated output as if it
were a second authoring source. The renderer uses the same compiler; no hidden
network fetch, expression evaluation, custom symbol map or template language.
Legacy `aria-notation: strict` diagrams still use the older exact-TeX validator;
new examples and CI require direct owner references. Refresh generated adapters
with the canonical glossary build after editing owners, before compiling diagrams.

## Mathematical grammar

Prefer the actual relation to a verbal paraphrase:

| Teaching job | Mathematical device | Shared owner example |
| --- | --- | --- |
| admissible candidates | set builder, membership, predicate | `eqs.rl.finite_action_set` |
| conditional selection | constrained argmax | `eqs.rl.qh_masked_argmax` |
| future reconstruction gain | finite sum, discount, horizon domain | `eqs.rl.finite_horizon_return` |
| off-policy continuation | argmax/evaluation separation and cases | `eqs.rl.qh_doubleq_index` |
| actor-state construction | equality / mapping | `eqs.rl.qh_representation_map` |
| spatial evidence read | membership, intersection, indexed pooling | `eqs.scene.candidate_query_pools` |
| feature interaction | attention, concatenation, elementwise product | `eqs.model.qh_a1_read`, `eqs.model.qh_feature_fusion` |
| uncertainty under compression | equality of conditional laws | `eqs.rl.qh_decision_sufficiency` |

Use mathematics for meaning, not to replace English with unexplained glyphs.
Introduce symbols before their diagram. A short title or caption may explain a
logical role, but no `predict(state, target, candidate)` string should stand in
for a registered value function. A whole scientific equation should not be
reduced to an output token just to fit a small box.

Full equations may have reusable rows. Extract them in the owning Typst module
and compose the aggregate from those rows. Their projections belong in the same
canonical facade and must preserve domains, bounds, indices and operations.
For example, A1's context read and its query/context/product fusion are distinct
rows of one shared mechanism. Do not maintain a diagram-only copy of either.

Exact matching alone does not certify meaning. Check projected equations against
the actual Typst body: old regional-pooling projections omitted membership sets,
and old Double-Q projections omitted terminal/empty-support cases. The regression
tests now guard these specific losses; they are not a general proof of equivalence.

## Typography and physical dimensions

Headings are normal `<b>` text, not `\textbf` inside KaTeX. Use CMU Serif and its
actual bold face for headings; KaTeX retains mathematical alphabets and weights.
Never globally bold formulas: scalar/vector/matrix distinctions can be semantic.

Start with 24 px math, 28 px headings, 22 px edge labels, 12 px padding, 16 px
node separation and 24 px rank spacing, at a declared width suited to its panel.
Source pixel sizes are not publication point sizes. For SVG width W:

`effective_pt = source_px * (width_mm * 72 / 25.4) / W`.

The inspector's existing floor is 9 pt base math/body, 11 pt titles and 8 pt
labelled edges at the declared width, within 230 mm height. Aim above those
floors. Subscripts naturally use smaller glyphs. Actual glyph/font/bounds checks
and a cold-read of the color and grayscale images remain necessary.

Break long equations in their canonical TeX projection with tested multi-row
layouts; do not delete a condition or force all expressions onto one line.
A portrait mathematical panel can use the page better than a wide collection
of tiny boxes. Split different explanatory views instead of lowering the floor
or fabricating edges. Whitespace separates mechanisms; node-area occupancy is
only a diagnostic, not an objective to maximize. See
[math-transport.md](math-transport.md) for the pinned host's alignment limitations.

The template's `.nodeLabel div { flex-direction: column; }` handles Mermaid's
mixed-math wrapper; block headings and `.katex-display { margin: 0; }` prevent
side-by-side title/formula placement and redundant vertical margins.

## Topology and scope

Retain the shared input/compute/data/output classes and dark-on-light palette.
Color is redundant: roles, enclosures, dashed borders and captions communicate
current versus proposed and actor versus oracle status in grayscale too.

An arrow means data flow, conditioning or a declared mathematical dependence.
Mark assumptions with dashed edges and explain them in the caption. A set
intersection is not merely two nearby boxes. A value label is not feasibility;
a candidate-conditioned readout is not an update to shared memory. Independent
controls must not look like additional inputs to the proposed model.

## Renderers

Mermaid math is KaTeX, not native Typst. The profile uses `forceLegacyMathML`
with the pinned CLI's matching KaTeX CSS/fonts. The inspector transiently loads
those assets and verifies glyph faces; it never distributes font files. Preview
hosts may lack fonts/CSS. Render the generated source before trusting a widget.
Browser SVG foreignObjects are not automatically portable Typst vectors. For
final inclusion use a verified export or a native Typst realization and inspect
the actual PDF page.

Primary references (checked 2026-09-06):
https://mermaid.js.org/config/math.html
https://typst.app/docs/reference/math/
https://typst.app/docs/reference/symbols/sym/
https://typst.app/docs/reference/math/cases/
