# Scientific Visualizations For ARIA-NBV

Use this reference for scientific, geometric, spatial, or 3D figures. Generic
captions, labels, tables, and Mermaid inclusion remain in `figures-tables.md`;
renderer setup remains in `packages/`; Rerun entity and frame behavior remains
with the `rerun-nbv-inspector` skill.

## Admissibility

A figure earns space by communicating a spatial relation, quantitative pattern,
evidence item, comparison, or falsifiable conceptual property more effectively
than prose or a compact table. Classify it on two independent axes before
drawing:

- **construction provenance**: schematic, measured, simulated, or reconstructed;
- **evidential role**: conceptual contract, hypothesis, qualitative evidence,
  or analyzed result.

The axes may combine: a simulated outcome can be an analyzed result, while a
measured artifact can be qualitative evidence. Merge or remove a figure that
only mirrors paragraph structure. Captions name the applicable provenance and
role and distinguish data-derived geometry, schematic construction, and
annotation.

## Renderer Routing

| Scientific role | Preferred renderer | Publication contract |
| --- | --- | --- |
| Sparse exact geometry, axes, rays, frusta, boxes, great circles | CeTZ | Vector source with Typst-native math; read `packages/cetz.md`. |
| Quantitative fields, complete-domain projections, publication plots | Matplotlib | Fixed data, axes, scales, and SVG/PDF export. Use 3D only for simple scenes with inspected depth order. |
| Interactive 3D exploration | Plotly | Freeze camera and scales before export; treat WebGL 3D inside SVG/PDF as raster content. |
| Real ARIA scenes, cameras, OBBs, meshes, points, trajectories | Rerun | Preserve recording, view specification, frame, and screenshot metadata; hand SDK work to `rerun-nbv-inspector`. |
| Architecture, process, topology, state transition | Fletcher or Mermaid | Use nodes and edges for relations rather than coordinate geometry. |
| Final panels, notation, labels, callouts, captions, alt text | Typst | Keep semantic text and mathematics editable and consistent with `docs/typst/shared`. |

Lilaq is the evaluated option for Typst-native quantitative plots. Treat
Plotsy-3D and Maquette as experimental candidates whose adoption requires a
compiled fixture, version record, and visual regression check.

## Geometry Contract

Before rendering, record or encode:

- coordinate frame or basis, handedness, and units;
- projection and fixed camera position, look target, and up direction;
- visibility, occlusion, and hidden-surface convention;
- measured, simulated, reconstructed, or schematic provenance;
- deterministic sampling or downsampling seed where applicable;
- the scientific quantity mapped to color, stroke, shape, size, or opacity.

Pair an oblique 3D context view with an orthographic, top, elevation, or
complete-domain view when occlusion hides relevant geometry. For spherical line
art, solid foreground arcs and light dashed rear arcs make visibility explicit.
Use coordinates derived from the declared geometry; decorative pseudo-3D and
arbitrary screen-space samples are inadmissible as scientific evidence.

## Spherical Domains

For a field or distribution on $S^2$:

1. Construct unit directions from the owning definition or data source.
2. Use an orthographic sphere to establish the frame and spatial relation.
3. Add a named complete-domain projection, such as Mollweide or
   equirectangular, when the full field matters.
4. Show numeric scale or colorbar, frame axes, and traceable observation and
   candidate markers.
5. Expose invariances and information loss declared by the representation,
   including antipodal symmetry when present.

Moments, histograms, kernels, and spherical harmonics communicate different
information. The figure and caption identify the representation actually used;
model-specific equations remain in `docs/typst/shared` and the owning thesis
section.

## Reproducible Hybrid Pipeline

A generated 3D base is complete when a provenance record, supplied by adjacent
source or manifest, contains:

- committed generation source and render command;
- input checksum or stable scene, sample, target, and frame identifiers;
- dependency versions;
- frame, units, camera, projection, and viewport;
- export format and raster scale;
- sampling seed, color limits, and palette;
- generated asset and Typst overlay paths;
- construction provenance and evidential role from the admissibility axes.

Prefer SVG/PDF for simple vector geometry and quantitative plots. Use an
intentional high-resolution PNG for dense WebGL or Rerun scene bases, then add
math and callouts in Typst. Describe mixed exports accurately when a nominal
SVG/PDF contains rasterized 3D layers.

## Visual Encoding And Accessibility

- Match a perceptually ordered sequential or diverging scale to the quantity.
- Reinforce important categories with shape, stroke, or labels as well as color.
- Give colorbars units, direction, and fixed limits when panels are compared.
- Use restrained transparency and direct scientific annotations; let the data
  carry the visual hierarchy.
- Inspect grayscale output and the final printed size.
- Give complex figures useful alt text or an adjacent textual interpretation
  covering composition, scales, values, and relationships.

## Primary Sources

Checked 2026-07-17. Refresh version-sensitive behavior before changing a
renderer integration.

| Source quality | Source | Establishes |
| --- | --- | --- |
| Official Typst | [Image formats and PDF constraints](https://typst.app/docs/reference/visualize/image/) and [visualization accessibility](https://typst.app/docs/reference/visualize/) | Supported assets, alt text, and export constraints. |
| Upstream CeTZ | [CeTZ 0.5.2](https://typst.app/universe/package/cetz/), [manual](https://cetz-package.github.io/docs/), [orthographic projection](https://cetz-package.github.io/docs/api/draw-functions/projections/ortho/), [3D coordinates](https://cetz-package.github.io/docs/basics/coordinate-systems/) | Typst-native geometry, projection, and coordinate behavior. |
| Typst Universe | [Lilaq](https://typst.app/universe/package/lilaq/) | Optional Typst-native quantitative plotting. |
| Upstream, experimental | [Plotsy-3D](https://typst.app/universe/package/plotsy-3d/), [repository](https://github.com/misskacie/plotsy-3d), and [Maquette](https://typst.app/universe/package/maquette/) | Candidate Typst 3D capabilities and maturity limits. |
| Official Plotly | [Static image export](https://plotly.com/python/static-image-export/) | Kaleido requirements and WebGL rasterization inside vector exports. |
| Official Rerun | [Blueprints](https://rerun.io/docs/concepts/visualization/blueprints) and [CLI](https://rerun.io/docs/reference/cli) | Separation of recording and view specification; scripted screenshots. |
| Official Matplotlib | [Geographic projections](https://matplotlib.org/stable/api/projections/geo.html) and [mplot3d limits](https://matplotlib.org/3.9.0/api/toolkits/mplot3d/faq.html) | Complete-domain projections and 3D depth-order caveats. |
| Publication guidance | [Nature figure specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) | Editable layers, legibility, restrained styling, and accessible color. |
| Peer-reviewed practice | [PLOS color guidance](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008259) | Perceptual palettes and avoidance of misleading rainbow scales. |
| Accessibility standard guidance | [W3C complex images](https://www.w3.org/WAI/tutorials/images/complex/) | Short and long descriptions for complex figures. |

## Completion Gate

The figure is ready only when its construction provenance, evidential role,
geometry contract, renderer lane, provenance record, visual encoding, and
final-size render have all been checked. Record any unavailable field or
skipped inspection explicitly.
