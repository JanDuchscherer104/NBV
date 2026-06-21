# Figures, Tables, And Captions For ARIA-NBV

## Role

Figures and tables are part of the argument. Each one must answer: what should
the reader learn that prose alone would not convey?

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

ARIA-NBV thesis/proposal tables use the Typst Universe `booktabs` package by
default. At the document root, import and enable it once:

```typst
#import "@preview/booktabs:0.0.4": *
#show: booktabs-default-table-style
```

Then include explicit rules in every publication-facing table:

```typst
#figure(
  table(
    columns: (1fr, 1fr, 1fr),
    toprule(),
    table.header([*Claim*], [*Evidence*], [*Decision*]),
    midrule(),
    [Target utility], [Endpoint target gain], [Primary metric],
    bottomrule(),
  ),
  caption: [Claim-to-evidence mapping.],
) <tab:claim-evidence>
```

For thesis result tables:

- include metric direction in header or caption;
- report mean and variability when available;
- bold only the best value when it is meaningful;
- do not duplicate all table values in prose;
- reference the conclusion, not the table object.

## Mermaid / Diagram Policy

- Keep `.mmd` as the version-controlled source.
- Render locally with Mermaid CLI, this skill's helper, or the ARIA-NBV Mermaid
  workflow if available.
- Include PNG/SVG/PDF with explicit Typst width.
- Inspect the standalone render and final Typst page.
- Use notation consistent with `docs/typst/shared`.

Typical proposal/thesis render command:

```bash
.agents/skills/typst-authoring/scripts/render_mermaid.sh \
  -i docs/typst/thesis/figures/proposal_system_flow.mmd \
  -o docs/typst/thesis/figures/proposal_system_flow.png \
  --width 1600
```

For Quarto pages, use `{mermaid}` fences instead of rendered PNG unless the
page explicitly needs a static export. For Typst proposal/thesis sources, do
not paste raw Mermaid; include the rendered asset and keep the `.mmd` beside
it.

## Visual QA Checklist

Before merging, check that labels are legible at printed thesis size, nothing
is clipped or blurry, figure width is appropriate, captions wrap cleanly,
cross-references resolve, symbols match shared notation, and page breaks do
not separate figures from necessary explanatory text awkwardly.
