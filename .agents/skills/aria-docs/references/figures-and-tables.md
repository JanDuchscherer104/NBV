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

For spatial visuals, record frame, units, handedness, projection, camera or
view parameters, visibility convention, deterministic sampling, and the
quantity encoded by color or glyph. Keep invalid categories outside scalar
utility color maps and reinforce critical categories with shape, stroke, or
labels as well as color.

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

## Publication Contract

- A figure should reveal a mechanism, comparison, geometry, relationship, or
  result that prose alone cannot convey.
- Captions identify the object or process, visual encoding, relevance,
  provenance, and evidential role.
- Tables carry exact values and compact comparisons; include metric direction
  and variability, and use the repository's Booktabs setup.
- Check grayscale behavior, contrast, clipping, text size, and legibility at
  final print or presentation size. Provide useful alt text or adjacent prose
  for complex figures.
- Preserve source, render command, stable input identifiers or checksums,
  dependency versions, fixed camera/export settings, seed, and color limits.

Inspect both the standalone asset and every affected document page.
