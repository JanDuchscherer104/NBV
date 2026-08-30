---
id: 2026-08-30_separate_3d_candidate_scene_semantic_channels
date: 2026-08-30
title: "Separate 3D Candidate Scene Semantic Channels"
status: done
topics: [thesis, figures, candidate-generation, camera-geometry, accessibility]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/figures/candidate_generation_geometry.typ
  - docs/typst/thesis/figures/candidate_generation_geometry.pdf
  - docs/typst/thesis/figures/data/candidate_scene_81286_000035.json
  - docs/typst/thesis/figures/scripts/export_candidate_scene_geometry.py
  - docs/typst/thesis/figures/scripts/recover_candidate_scene_calibration.py
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
  - docs/typst/thesis/main.pdf
  - scripts/tests/test_typst_authoring_hygiene.py
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 82cec7838e5e6b34434143ba1ef32481daf79bce
repo_branch: "codex/thesis-figure-candidate-3d-semantic-palette"
worktree_kind: linked
---

## Task
Repair the candidate-generation 3D figure after user review showed that the
processed mesh, observed trajectory, and camera frusta did not remain
perceptually distinct at final thesis size.

## Method
Preserved exact geometry and a final-size baseline, generated two parallel
palette candidates, rejected the label-heavy variant, and integrated one
bounded semantic-encoding revision. Inspected standalone and embedded color and
grayscale renders, then iterated through independent visual and scientific
review until both approved the exact candidate.

## Findings
- Nominally different purple and teal overlays still approached mesh edges and
  one another in grayscale. The accepted figure uses an arrowed magenta history
  path, dark-blue dashed logged-camera frusta, black sampling root and selected
  frustum, orange double OBB, and existing family shapes.
- Exact review exposed that the current physical RGB endpoint and canonical
  sampling root project only 0.174 mm apart at final size. A larger hollow
  physical-pose ring drawn after a smaller filled root point preserves both
  exact coordinates and makes their frame distinction visible.
- Generator-owned prose now self-identifies the selected candidate pose in the
  primary exporter, recovery generator, and regenerated pinned JSON.
- Exact-head GitHub review found that historical-frustum row indices lived only
  in recovery provenance. Both export paths now emit the indices in the shared
  oblique-panel payload, and the CeTZ consumer reads that portable contract.
- No mesh, OBB, camera, candidate, validity, count, or family geometry changed.

## Commits
- [f9c1f3c8f9036e7ce17a6e25b46a3e3b69682562](https://github.com/JanDuchscherer104/ARIA-NBV/commit/f9c1f3c8f9036e7ce17a6e25b46a3e3b69682562) — separate semantic channels, preserve frame-distinct near-coincident poses, clarify generated provenance, and rebuild the rendered figure and thesis.
- [82cec7838e5e6b34434143ba1ef32481daf79bce](https://github.com/JanDuchscherer104/ARIA-NBV/commit/82cec7838e5e6b34434143ba1ef32481daf79bce) — move historical-frustum row indices into the shared panel contract and add its authoring regression test.

## Verification
- Ruff format/check and Python compilation passed for both geometry generators.
- The authoring hygiene suite passes 22 tests, including the primary/recovery
  exporter portability contract for historical-frustum row indices.
- Recovery regeneration from the pinned primary-worktree raw shard was
  byte-stable across two runs.
- `make thesis-pdf`, `make thesis-pdf-ci`,
  `make typst-authoring-contract`, `make thesis-marker-contract`, and
  `git diff --check` passed. The figure is one 160 x 72.5 mm page; the thesis
  remains 123 A4 pages.
- Exact final-size color/grayscale review and independent scientific review
  both approved with zero P0--P2 findings.

## Canonical Owner Impact
The tracked CeTZ source owns semantic styling and glyph composition. The
exporter and recovery generator own portable provenance strings; the regenerated
JSON projects the recovery path. The section owns alternative text, caption,
and interpretation, while both PDF files are rebuilt artifacts.
