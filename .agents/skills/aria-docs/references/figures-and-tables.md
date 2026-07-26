# Figures, Tables, And Scientific Visuals

Use this branch for figures, tables, captions, geometric visualizations, and
rendered evidence. Preserve the construction source and the scientific contract
that makes the visual interpretable.

## Admissibility

Classify each visual on two independent axes:

- construction provenance: schematic, measured, simulated, or reconstructed;
- evidential role: conceptual contract, hypothesis, qualitative evidence, or
  analyzed result.

Record both where confusion could change the claim. A measured artifact is not
automatically an analyzed result, and a simulation is not automatically a
schematic.

Use source-derived or explicitly constructed scientific visuals by default.
Use generated bitmap imagery only when the user explicitly requests it; never
substitute it for measured evidence, reproducible geometry, or a quantitative
plot.

For spatial visuals, record frame, units, handedness, projection, camera or
view parameters, visibility convention, deterministic sampling, and the
quantity encoded by color or glyph. Keep invalid categories outside scalar
utility color maps and reinforce critical categories with shape, stroke, or
labels as well as color.

Coordinates and overlays must come from the owning geometry or data source;
do not hand-place witnesses or retain generic camera coordinates when a visual
claims calibrated geometry. Use solid foreground and visibly distinct hidden
segments when line-of-sight matters.

## Renderer Choice

| Scientific role | Preferred surface |
| --- | --- |
| Architecture, process, topology, state transition | Mermaid or Fletcher |
| Sparse exact geometry, axes, rays, boxes, frusta | CeTZ |
| Sparse typed 3D vector geometry | Scenery |
| Moderate local PLY/OBJ/STL mesh | Maquette SVG |
| Dense or occluded scene geometry | PyTorch3D, Rerun, or another z-buffered raster source |
| Quantitative plot or complete-domain projection | Matplotlib |
| Exploratory interactive plot with a frozen export view | Plotly |
| Final labels, notation, callouts, composition, and caption | Typst |

Do not use decorative pseudo-3D where depth order, occlusion, metric scale, or
projection carries evidence. Pair an oblique view with an orthographic or
complete-domain view when occlusion hides the relationship being claimed.

For spherical data, show the representation actually stored. Use unit rays for
discrete directions, name any complete-domain projection, include numeric
scale, and expose lost invariances. Equal azimuth/elevation bins are not equal
area; use an equal-area construction when directional counts or coverage are
the quantity. Do not invent a smooth field or harmonic basis absent from the
source data or method.

## Publication Contract

- A figure should reveal a mechanism, comparison, geometry, relationship, or
  result that prose alone cannot convey.
- Captions identify the object or process, visual encoding, relevance,
  provenance, and evidential role.
- Use explicit size and stable labels: `<fig:...>`, `<tab:...>`, `<eq:...>`,
  and `<sec:...>`. State the scientific conclusion in prose and attach the
  reference instead of writing only “Figure X shows”.
- Tables carry exact values and compact comparisons; include metric direction
  and variability, use `table.header` for accessible headers, and include
  deliberate `toprule()`, `midrule()`, and `bottomrule()` Booktabs rules.
  Bold only a meaningful best value and do not repeat every cell in prose.
- Check grayscale behavior, contrast, clipping, text size, and legibility at
  final print or presentation size. Provide useful alt text or adjacent prose
  for complex figures.
- Preserve source, render command, stable input identifiers or checksums,
  dependency versions, fixed camera/export settings, seed, and color limits.
- Prefer SVG/PDF for simple vector geometry and quantitative plots. Use an
  intentional high-resolution raster for dense WebGL or z-buffered scene
  layers, then retain editable labels and math in Typst. Describe mixed exports
  honestly when a nominal vector file contains rasterized layers.

Inspect both the standalone asset and every affected document page.
