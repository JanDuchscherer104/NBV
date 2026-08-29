# Figures, Tables, And Captions For ARIA-NBV

## Role

Figures and tables are part of the argument. Each one must answer: what should
the reader learn that prose alone would not convey?

Scientific, geometric, spatial, and 3D renderer routing is covered by the
skill's direct conditional route to `scientific-visualizations.md`.

## Figure Policy

Use `#figure(...)` with explicit sizing and labels:

```typst
#figure(
  image("figures/vin_offline_store_training.png", width: 92%),
  caption: [Offline training pipeline for the VIN proxy. Logged observations define historical context, counterfactual candidate views are rendered from sampled poses, and oracle RRI labels supervise candidate scoring.],
) <fig:vin-offline-store-training>
```

Captions should contain:

1. object/process being shown;
2. key visual encoding or stages;
3. thesis relevance;
4. no unsupported result claim unless backed by data.

Label conventions:

- Figures: `<fig:short-slug>`
- Tables: `<tab:short-slug>`
- Equations: `<eq:short-slug>`
- Sections: `<sec:short-slug>`

In prose, avoid bare "Figure X shows..." phrasing. State the claim and attach
the reference, for example: "The offline-store pipeline separates historical
context from counterfactual candidate rendering (@fig:vin-offline-store)."

## Table Policy

Use tables for exact values and compact comparisons. Use figures for trends,
architecture, flow, or spatial relationships.

Active ARIA-NBV scientific tables use the shared presentation owner at
`docs/typst/shared/tables.typ`. Import the constructor matching the surface:

```typst
#import "../../shared/tables.typ": publication-table
```

Use `publication-table` for papers and thesis sections, `development-table` for
development-only reports, and `presentation-table` for slides. Keep columns,
rows, alignment, captions, and labels at the call site; the shared owner emits
the semantic header and restrained Booktabs rules:

```typst
#figure(
  publication-table(
    columns: (1fr, 1fr, 1fr),
    header: ([*Claim*], [*Evidence*], [*Decision*]),
    rows: (
      [Target utility], [Endpoint target gain], [Primary metric],
    ),
  ),
  caption: [Claim-to-evidence mapping.],
) <tab:claim-evidence>
```

The structural title-page helper remains local layout. Archived sources and
package manuals remain historical/reference material. Run
`make typst-authoring-contract` after changing any active table surface.

For thesis result tables:

- include metric direction in header or caption;
- report mean and variability when available;
- bold only the best value when it is meaningful;
- do not duplicate all table values in prose;
- reference the conclusion, not the table object.

## Conceptual Diagram Policy

Use `aria-nbv-mermaid` first for the concept brief, explanatory-depth review,
retain/revise/remove decision, and Mermaid-vs-Typst route for relational work.
The exact scientific, geometric, spatial, 3D, or quantitative renderer remains owned by
[`scientific-visualizations.md`](scientific-visualizations.md#renderer-routing).

`typst-authoring` owns accepted Typst source realization, figure inclusion,
captions, labels, compilation, and final-page inspection. Keep `.mmd` as the
source of record only for Mermaid-native figures; `tools/mermaid` remains the
sole local Mermaid lint/render wrapper. Include external PNG/SVG/PDF assets with
explicit Typst width, inspect standalone and final-page renders, and use notation
from `docs/typst/shared`.

For Mermaid lint/render commands and failure behavior, follow the conditional
[`mermaid-native.md`](../../aria-nbv-mermaid/references/mermaid-native.md)
branch; do not duplicate the wrapper contract here.

For Quarto pages, use `{mermaid}` fences instead of rendered PNG unless the page
explicitly needs a static export. For an intentional Mermaid-backed Typst asset,
do not paste raw Mermaid; include the rendered asset and keep the `.mmd` beside
it. Do not create Mermaid intermediates for Fletcher/CeTZ-native figures.

## Visual QA Checklist

Before merging, check that labels are legible at printed thesis size, nothing
is clipped or blurry, figure width is appropriate, captions wrap cleanly,
cross-references resolve, symbols match shared notation, and page breaks do
not separate figures from necessary explanatory text awkwardly. For scientific
figures also check frame, units, projection, quantitative scale/colorbar,
source provenance, grayscale readability, and final printed size.
