---
id: 2026-08-30_calibrate_candidate_geometry_thesis_figures
date: 2026-08-30
title: "Calibrate candidate geometry thesis figures"
status: done
topics: [thesis, typst, figures, geometry, calibration, candidates]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/shared/equations/action.typ
  - docs/typst/shared/equations.typ
  - docs/typst/thesis/figures/candidate_family_geometry.typ
  - docs/typst/thesis/figures/candidate_generation_geometry.typ
  - docs/typst/thesis/figures/scripts/export_candidate_scene_geometry.py
  - docs/typst/thesis/figures/scripts/recover_candidate_scene_calibration.py
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 7fc7e488dba6d46a3721b9447b55b61890ca0fb0
repo_branch: "codex/thesis-figure-candidate-generation-geometry"
worktree_kind: linked
---

## Task

Replace the dense candidate-generation thesis schematic with conceptually clean
family geometry and a calibrated 3D scene-grounding figure while preserving the
pinned finite-shell contract.

## Method

Reviewed the figure from professor and student perspectives, checked the camera
and sampling-frame owners, rendered the processed ASE GT mesh and target OBB,
recovered the pinned root and selected camera from the preserved projection, and
constructed all-valid Fisheye624 outlines through `CameraTW.unproject`. Iterated
the CeTZ layout at final A4 size in color and direct-Poppler grayscale. Compared
the result with `origin/main` and the stacked PR #199 parent, then ran independent
scientific, visual, and reproducibility verification.

## Findings

- `candidate_family_geometry.typ` now explains the three core center transforms,
  base-gaze rule, and bounded view jitter without mixing in feasibility or
  selection.
- `candidate_generation_geometry.typ` now separates the neutral processed GT
  mesh, selected oracle-task GT OBB, physical RGB history/frusta, canonical
  sampling root, selected hypothetical view, and complete-shell BEV audit.
- The physical RGB pose and candidate-sampling frame differ by approximately
  `0.0137 m` and `92.5449 deg`; the sampling root is therefore an anchor rather
  than a physical RGB frustum.
- The tracked recovery path regenerates both calibrated JSON and the exact
  publication crop when the original rollout Zarr is unavailable. It explicitly
  classifies family markers as reconstructed configured blocks because the
  stored `position_id` rows cannot be re-read on this host.
- Exact-head review found that CLI raster/crop overrides were not propagated to
  JSON references and checksums. The recovery owner now derives the background
  path and hashes from the resolved override assets.
- Exact-head rereview found that the cross-format equation registry still
  exported the former fixed shell size and radius interval. The registry now
  matches the modular Typst bodies, and all notation adapters were regenerated.
- A subsequent rereview found that the primary exporter did not prove the raw
  camera shard and rollout store shared one sampling root. A single frame-owner
  assertion now gates both primary and recovery exports before rendering.
- The color-role follow-up rereview found that the static caption could retain
  the recovery disclaimer after a primary export. Both exporters now emit a
  concise `family_display` provenance sentence, and the caption and alternative
  text consume the active JSON value.
- Semantic roles remain distinct in color and grayscale: neutral mesh, solid
  purple physical trajectory, teal dashed historical frusta, orange double-line
  OBB, family-shaped shell markers, and black/gold selection.

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/7fc7e488dba6d46a3721b9447b55b61890ca0fb0
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/fe651e06093f242d8c0b62a3bcd5b193df3ae7a7
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/6eb42262924ce2b60c475a8de10a709eb0708254
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/e13253c546859bad18e890842d6cfceba3360848
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/5d5add406f74625f0a10f6edfe9b01fea2337645
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/83ccf6545667dd0a51b35d3a895626f007fec2f6

## Verification

- recovery run twice: calibrated JSON and crop remained byte-identical;
- standalone Typst figure: one `160 x 72.5 mm` page;
- full thesis: 122 A4 pages, page 58 inspected in color and grayscale;
- `make thesis-pdf-ci`, `make typst-authoring-contract`, and
  `make thesis-marker-contract`: pass;
- Python `py_compile`, Ruff check/format check, and `git diff --check`: pass;
- independent scientific review: approve, zero P0--P2;
- independent visual review: pass, zero P0--P2;
- exact reproducibility review: pass.
- custom `--oblique-raster`, `--crop-output`, and `--output` recovery: emitted
  background reference and both SHA-256 records match the resolved override
  files.
- `make glossary` run twice: canonical registry and Quarto, Typst, and Lua
  adapters remain byte-stable and contain the component-resolved shell and
  radius equations.
- canonical sampling-root assertion: pinned raw history and recovered root pass;
  a synthetic one-metre root mismatch raises before evidence generation.
- recovery run twice after the provenance-caption fix: JSON and publication crop
  are byte-stable; the rendered caption resolves to the recovery disclaimer,
  while the primary exporter owns its stored-`position_id` wording.

The original rollout Zarr remains unavailable locally, so the primary exporter
cannot be executed end to end. The tracked recovery path and published caption
state this provenance limitation explicitly.

## Canonical Owner Impact

The shared action equations now parameterize shell count and component-specific
radius support. The thesis section and its two Typst figure sources own the
accepted explanatory narrative. The normal and recovery exporters own the
rendered-scene provenance and calibration procedure. No further canonical owner
update is needed for this workpackage.
