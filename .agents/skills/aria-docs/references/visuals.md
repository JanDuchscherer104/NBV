# Figures, Tables, Scientific Visuals, And Slides

Read this file when a change affects a figure, table, caption, scientific or
geometric visualization, or Typst slide deck.

Before creating a visual, inspect a nearby accepted source under
`docs/typst/thesis/figures/`, its optional `data/` or `scripts/` input, and the
shared Typst helpers. Extend an existing reproducible construction pattern when
it fits; do not copy rendered output and discard its source or view metadata.

Classify a proposed figure on two independent axes:

- construction provenance: schematic, measured, simulated, or reconstructed;
- evidential role: conceptual contract, hypothesis, qualitative evidence, or
  analyzed result.

Name both in the caption or adjacent provenance when ambiguity could change the
reader's interpretation. A measured artifact is not automatically an analyzed
result, and a simulated result is not automatically a conceptual schematic.

## Figure And Caption Contract

A figure is part of the argument. It must reveal a mechanism, comparison,
geometry, data relationship, or result that prose alone cannot convey.

- Use explicit size, caption, and `<fig:short-slug>` label.
- State the object or process, the visual encoding, and why it matters.
- State whether the content is schematic, simulated, reconstructed, measured,
  or derived from another source.
- Do not imply an empirical result from a conceptual illustration.
- In prose, state the conclusion and attach the reference; avoid bare
  "Figure X shows" narration.
- Inspect legibility at final printed size, grayscale behavior, clipping,
  caption wrapping, and page placement.

Use `<tab:short-slug>`, `<eq:short-slug>`, and `<sec:short-slug>` for other
cross-reference classes.

## Tables

Use tables for exact values and compact comparisons; use figures for trends,
architecture, process, and spatial relationships. Publication-facing tables use
the existing Booktabs setup:

```typst
#import "@preview/booktabs:0.0.4": *
#show: booktabs-default-table-style
```

Use `toprule()`, `midrule()`, and `bottomrule()` deliberately. Include metric
direction in the header or caption, report variability where available, bold
only a meaningful best value, and discuss the conclusion rather than repeating
every cell in prose.

## Scientific And Geometric Visuals

Choose the renderer by scientific role:

| Role | Preferred surface |
| --- | --- |
| Architecture, process, topology, state transitions | Mermaid |
| Exact vector geometry, axes, rays, frusta, boxes | CeTZ or existing Typst vector source |
| Quantitative plots and complete-domain projections | Matplotlib with fixed data and axes |
| Real ARIA scenes, cameras, OBBs, meshes, points, trajectories | Rerun with recording/view metadata |
| Final composition, notation, labels, callouts, captions | Typst |

Before rendering, record the coordinate frame, handedness, units, projection,
camera position/look target/up direction, visibility convention, deterministic
sampling seed, quantity-to-color mapping, and source provenance. Pair an
oblique 3D view with an orthographic or complete-domain view when occlusion
hides the scientific relationship. Never use perspective decoration where a
quantitative projection is required.

Keep reproducible source and fixed export settings beside or traceably linked
to the asset. Inspect both the standalone render and the final document page.

### ARIA Geometry Safeguards

- Publication camera frusta derive calibrated image-boundary rays from
  `aria_nbv/aria_nbv/rerun_inspector/_frusta.py`. The inscribed-square helper
  `utils/data_plotting.py::get_frustum_segments` is diagnostic geometry, not
  the publication owner.
- A pyramidal frustum implies a linear or rectified camera. If a figure omits
  ARIA fisheye distortion, state that approximation in the figure or caption.
- For data on the sphere, show the representation actually stored. Use unit
  rays for discrete directions; do not invent a smooth field or
  spherical-harmonic lobe. Equal azimuth/elevation bins are not equal area.
  Use and name an equal-area or complete-domain projection when counts or
  coverage over the full sphere matter.
- Candidate invalidity is a separate hard category. Encode it with glyph,
  stroke, or label in addition to color, and keep invalid rows outside scalar
  utility color maps.
- Rerun recording, camera/frustum, frame, and blueprint implementation belongs
  to `rerun-nbv-inspector`; `aria-docs` owns the exported figure's scientific
  argument, caption, final composition, and rendered-page QA.

## Mermaid Inclusion

Read `mermaid.md`. Keep `.mmd` as source. Quarto normally uses a `{mermaid}`
fence; Typst includes a locally rendered SVG/PDF/PNG with explicit width. Do
not paste raw Mermaid into Typst.

## Slides

Inspect the target deck and `docs/typst/shared/slide-template.typ` before
changing theme or macros. Preserve the deck's existing package/template
contract rather than importing an old archived template.

- One slide should have one primary claim or decision.
- Prefer a visual plus concise evidence over manuscript paragraphs.
- Keep symbols, glossary terms, colors, and citations consistent with the
  thesis.
- Use progressive reveals only when order carries meaning; do not hide
  comparison context or reserve unstable layout accidentally.
- Keep captions and source labels readable at presentation distance.
- Put detailed methods, backup evidence, and secondary derivations in appendix
  slides.

Compile the owning deck, export affected pages to PNG with Typst's `--pages`
and `--ppi` options, and inspect for overflow, tiny labels, alignment, contrast,
and reveal-independent layout.
