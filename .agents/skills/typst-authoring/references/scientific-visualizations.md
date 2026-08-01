# Scientific Visualizations For ARIA-NBV

Use this reference for scientific, geometric, spatial, or 3D figures. Generic
captions, labels, tables, and Mermaid inclusion remain in `figures-tables.md`;
renderer setup remains in `packages/`; Rerun entity and frame behavior remains
with `aria_nbv/aria_nbv/rerun_inspector/README.md`.

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
| Typed sparse 3D scenes with depth-sorted faces and hidden-line clipping | Scenery | Pure vector CeTZ output; fixture-gate the 0.x package and read `packages/scenery.md`. |
| Low- or medium-poly local PLY, OBJ, or STL meshes | Maquette SVG | Painter-sorted vector mesh; freeze projection, camera, shading, and decimation; read `packages/maquette.md`. |
| Dense or strongly intersecting local meshes | Maquette PNG, Rerun, or PyTorch3D | Use a z-buffered raster base and retain vector labels, axes, frusta, and callouts in Typst. |
| Quantitative fields, complete-domain projections, publication plots | Matplotlib | Fixed data, axes, scales, and SVG/PDF export. Use 3D only for simple scenes with inspected depth order. |
| Interactive 3D exploration | Plotly | Freeze camera and scales before export; treat WebGL 3D inside SVG/PDF as raster content. |
| Real ARIA scenes, cameras, OBBs, meshes, points, trajectories | Rerun | Preserve recording, view specification, frame, and screenshot metadata; use the inspector README, implementation, and focused tests for SDK work. |
| Architecture, process, topology, state transition | Fletcher or Mermaid | Use nodes and edges for relations rather than coordinate geometry. |
| Final panels, notation, labels, callouts, captions, alt text | Typst | Keep semantic text and mathematics editable and consistent with `docs/typst/shared`. |

Lilaq is the evaluated option for Typst-native quantitative plots. Scenery and
Maquette have compiled project fixtures, but both remain young 0.x packages:
pin their versions, keep the fixtures, and visually inspect every upgraded
render. Treat Plotsy-3D as an unevaluated experimental candidate.

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

For ARIA camera figures, derive calibrated image-boundary rays from
`aria_nbv/aria_nbv/rerun_inspector/_frusta.py`. The older
`utils/data_plotting.py::get_frustum_segments` inscribes a diagnostic square in
the valid image radius and normalizes rays to an arbitrary length; it is useful
for exploration but is not the publication geometry owner. A pyramidal frustum
also implies a linear or rectified camera. If fisheye distortion is omitted,
the figure and caption state that approximation.

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

Equal azimuth/elevation bins do not have equal solid angle. Use an equal-area
construction such as HEALPix when counts or coverage per direction are the
quantity of interest, and pair the 3D sphere with a numeric Mollweide or native
HEALPix map. Use discrete rays when the stored representation is only a set of
directions; do not draw a smooth field or spherical-harmonic lobe unless that
estimator or basis is actually present.

## Source-Derived Construction Patterns

Mine local TeX and figure captions for *composition patterns*, not artwork to
copy. Confirm that the imported pattern serves ARIA-NBV's own quantity and
contract.

| Local primary source | Reusable construction pattern | ARIA-NBV constraint |
| --- | --- | --- |
| `docs/literature/tex-src/arXiv-SCONE/camera_ready_2_approach.tex` | Separate target-centred camera history, proxy support, and an $S^2$ visibility field. | Show the representation actually stored; spherical harmonics remain a hypothesis until implemented. |
| `docs/literature/tex-src/arXiv-FisherRF/sec/intro.tex` | Pair a complete viewing-sphere scalar field with a few discrete candidate views. | Map ARIA-NBV coverage, RRI, or headroom—not Fisher information—and include numeric scale. |
| `docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex` | Use top-down ASE context with OBBs, point evidence, and Aria trajectory. | Preserve world frame, metric scale, scene/sample/target provenance, and an oblique companion when height matters. |
| `docs/literature/tex-src/arXiv-scene-script/sections/structured_scene_language.tex` | Pair bird's-eye scene context with ego-centric or modality close-ups. | Keep all panels on one named sample and explain what each modality contributes. |
| `docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex` | Separate normal, depth, visibility-count, and empty-space evidence. | Do not compress distinct measured quantities into decorative multicolour geometry. |
| `docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex` | Use one transformation per panel: transform, depth-sort, project, aggregate. | Treat PB-NBV as finite projection-based proposal/scoring, not continuous control or ARIA ground truth. |
| `docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/4_experiment_ver3_rpm.tex` | Compare target-conditioned choices with actual scene geometry and camera frusta. | Derive frusta and target identity from the same frozen ARIA sample; do not substitute generic icon cameras. |

## Permissive Vector-Primitive Precedents

Adopt topology and interaction grammar from permissively licensed upstream
implementations, then regenerate every coordinate from ARIA-NBV's typed data.
Do not copy a viewer screenshot or retain generic pinhole coordinates when the
figure claims calibrated ARIA geometry.

| Upstream source | License | Primitive to adapt | ARIA-NBV use rule |
| --- | --- | --- | --- |
| [EFM3D `viz.py`](https://github.com/facebookresearch/efm3d/blob/main/efm3d/utils/viz.py) and [`obb.py`](https://github.com/facebookresearch/efm3d/blob/main/efm3d/aria/obb.py) | Apache-2.0 | Scene evidence, metric trajectory, current camera, thinned historical cameras, and 12-edge OBBs. | Primary composition precedent for real ASE context. Keep one target accent and disclose frame and scale. |
| [Viser camera frustum](https://github.com/nerfstudio-project/viser/blob/main/src/viser/client/src/CameraFrustumVariants.tsx) | Apache-2.0 | Five-vertex wire camera with four image-plane edges, four centre rays, and a small up-direction tick. | Use as a sparse repeated glyph. A lone filled frustum is not a thesis figure. |
| [pytransform3d camera artist](https://github.com/dfki-ric/pytransform3d/blob/master/pytransform3d/plot_utils/_artists.py) and [trajectory example](https://dfki-ric.github.io/pytransform3d/_auto_examples/plots/plot_camera_trajectory.html) | BSD-3-Clause | Metric camera trajectory, periodic frames, calibrated image plane, and top-edge orientation cue. | Thin history deterministically and keep equal metric axes. |
| [Open3D `LineSet::CreateCameraVisualization`](https://github.com/isl-org/Open3D/blob/main/cpp/open3d/geometry/LineSetFactory.cpp) | MIT | Calibrated camera, OBB, line-set, and correspondence topology. | Prefer line sets for analytic overlays; retain the camera convention used to construct the coordinates. |
| [PyTorch3D camera plotting](https://github.com/facebookresearch/pytorch3d/blob/main/pytorch3d/vis/plotly_vis.py) | BSD-style | Compact batched wire cameras for large pose sets. | Borrow topology only; source intrinsics and world-from-camera transforms from ARIA data. |
| [Trimesh proximity](https://trimesh.org/trimesh.proximity.html) | MIT | Closest surface point, distance, and triangle identifier. | Compute metric witnesses; never hand-place point--triangle correspondence lines. |

For finite-candidate figures, combine the EFM3D scene grammar with a sparse
Viser/Open3D camera glyph: dense geometry is a reproducible raster base, while
the target OBB, trajectory, candidate status, selected path, and camera
wireframes remain vector. Show the full candidate set at least once through
centres or compact glyphs, but thin full frusta in occluded oblique views.
Encode invalidity by glyph or stroke as well as colour, and keep invalid rows
outside any scalar utility colour map.

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

Checked 2026-07-19. Refresh version-sensitive behavior before changing a
renderer integration.

| Source quality | Source | Establishes |
| --- | --- | --- |
| Official Typst | [Image formats and PDF constraints](https://typst.app/docs/reference/visualize/image/) and [visualization accessibility](https://typst.app/docs/reference/visualize/) | Supported assets, alt text, and export constraints. |
| Upstream CeTZ | [CeTZ 0.5.2](https://typst.app/universe/package/cetz/), [manual](https://cetz-package.github.io/docs/), [orthographic projection](https://cetz-package.github.io/docs/api/draw-functions/projections/ortho/), [3D coordinates](https://cetz-package.github.io/docs/basics/coordinate-systems/) | Typst-native geometry, projection, and coordinate behavior. |
| Upstream Scenery | [Scenery 0.1.0](https://typst.app/universe/package/scenery/) and [repository](https://github.com/GiggleLiu/scenery) | Typed 2D/3D primitives, orthographic/perspective cameras, depth sorting, partial hidden-line clipping, and explicit painter/near-plane limits. |
| Upstream Maquette | [Maquette 0.1.1](https://typst.app/universe/package/maquette/) and [repository](https://github.com/bernsteining/maquette) | Compile-time PLY/OBJ/STL rendering; painter-sorted SVG for moderate meshes and z-buffered PNG for dense meshes. |
| Typst Universe | [Lilaq](https://typst.app/universe/package/lilaq/) | Optional Typst-native quantitative plotting. |
| Upstream, experimental | [Plotsy-3D](https://typst.app/universe/package/plotsy-3d/) and [repository](https://github.com/misskacie/plotsy-3d) | Candidate Typst 3D capabilities and maturity limits. |
| Official Plotly | [Static image export](https://plotly.com/python/static-image-export/) | Kaleido requirements and WebGL rasterization inside vector exports. |
| Official Rerun | [Blueprints](https://rerun.io/docs/concepts/visualization/blueprints) and [CLI](https://rerun.io/docs/reference/cli) | Separation of recording and view specification; scripted screenshots. |
| Official Matplotlib | [Geographic projections](https://matplotlib.org/stable/api/projections/geo.html) and [mplot3d limits](https://matplotlib.org/3.9.0/api/toolkits/mplot3d/faq.html) | Complete-domain projections and 3D depth-order caveats. |
| Upstream HEALPix | [HEALPix introduction](https://healpix.sourceforge.io/doc/html/intro.htm) and [geometry](https://healpix.sourceforge.io/doc/html/intro_Geometric_Algebraic_Propert.htm) | Equal-area, iso-latitude spherical cells for direction counts or coverage. |
| Peer-reviewed illustration practice | [Gooch et al. (1998)](https://doi.org/10.1145/280814.280950) | Shape-revealing cool-to-warm technical shading without photorealistic gloss. |
| Publication guidance | [Nature figure specifications](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) | Editable layers, legibility, restrained styling, and accessible color. |
| Peer-reviewed practice | [PLOS color guidance](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008259) | Perceptual palettes and avoidance of misleading rainbow scales. |
| Accessibility standard guidance | [W3C complex images](https://www.w3.org/WAI/tutorials/images/complex/) | Short and long descriptions for complex figures. |

## Completion Gate

The figure is ready only when its construction provenance, evidential role,
geometry contract, renderer lane, provenance record, visual encoding, and
final-size render have all been checked. Record any unavailable field or
skipped inspection explicitly.
