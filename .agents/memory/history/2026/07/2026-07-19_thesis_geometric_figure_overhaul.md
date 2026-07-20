---
id: 2026-07-19_thesis_geometric_figure_overhaul
date: 2026-07-19
title: "Thesis Geometric Figure Overhaul"
status: done
topics: [thesis, typst, figures, geometry, ase, reproducibility]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/figures
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/sections/06-draft-open-work.typ
  - .agents/skills/typst-authoring/references
---

## Task

Replace geometric thesis illustrations that treated an isolated camera frustum
or an arbitrary decimated mesh as the subject. Ground the replacements in
measured local evidence, adopt permissively licensed scientific-visualization
primitives, and keep implementation-dependent directional memory outside the
submission claim surface.

## Decisions and outputs

- Removed the isolated camera-boundary figure and the separate candidate-validity
  cartoon. A frustum is now a repeated wire glyph inside a complete decision
  composition: logged trajectory, target OBB, candidate set, hard validity, and
  selected action.
- Added a reproducible hybrid figure for ASE scene 81286, sample
  `ASE_81286_Atek_000035`, rollout row 73, and step row 121. Open3D z-buffers the
  dense scene while CeTZ retains OBBs, paths, candidate centres, status glyphs,
  and thinned wire frusta as vector geometry. The bird's-eye panel retains all
  60 candidate centres: 25 valid and 35 clearance-invalid.
- Replaced the visually dense sofa metric panel with a controlled point-mesh
  fixture. Exact Trimesh closest-point witnesses and the repository PyTorch3D
  metric hold the support and five points fixed while changing only the face
  table. Equal-face completeness changes from 0.03640 to 0.02284 square metres;
  accuracy remains 0.00640 square metres.
- Retained the target-task sampler as the implementation-faithful contract
  diagram. Moved the S2 directional-memory composition into the marked
  development diary as hypothesis/ablation material. It shows the same logged
  directions on a wire sphere and equal-area Mollweide map and makes no learned,
  smooth-field, or spherical-harmonic claim.
- Extended the Typst authoring references with renderer routing, licensed
  primitive sources, Scenery and Maquette smoke fixtures, and the rule that
  dense surfaces should be raster while analytical overlays remain vector.

## Verification

- Replayed all three Python exporters against the pinned local stores and mesh.
- `ruff format` and `ruff check` passed for all exporter scripts.
- Compiled the four touched thesis figures and the Scenery and Maquette fixtures
  with Typst.
- `make thesis-pdf` produced a 76-page development PDF; pages 39, 42, and 74
  were visually inspected after the final render.
- Submission-mode compilation fails closed at the required explicit evidence
  bundle. Independently compiling the diary section in submission mode fails at
  the first unresolved internal marker.
- The local skill validator passed and `git diff --check` passed.
- `make kg-claim-check` could not run because the isolated worktree lacks
  `.agents/external/litkg-rs/Cargo.toml`; the strengthened metric statement is
  instead backed by the freshly replayed controlled fixture. Tinymist is not
  installed in this environment.

## Canonical state impact

No research-direction or implementation contract changed. This work changes
the manuscript's evidential presentation and the reusable visualization
guidance only.
