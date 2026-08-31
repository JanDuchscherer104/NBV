---
id: 2026-08-30_explain_target_rri_point_mesh_metric
date: 2026-08-30
title: "Explain target-RRI point--mesh metric"
status: done
topics: [thesis, figures, target-rri, point-mesh, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/figures/data/point_mesh_metric_fixture.json
  - docs/typst/thesis/figures/scripts/export_point_mesh_metric_fixture.py
  - docs/typst/thesis/figures/target_rri_point_mesh_geometry.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 04d481b93bfac45487ea675abb6f76ef118dd3e1
repo_branch: "codex/thesis-figure-target-rri-geometry"
worktree_kind: linked
---

## Task

Revise the target-RRI point--mesh figure so it cleanly explains the exact
point-to-triangle primitive, the two asymmetric reduction populations, and the
tessellation sensitivity of equal-face completeness.

## Method

Mapped the figure to the canonical equations, PyTorch3D point--mesh owner,
oracle callers, and deterministic synthetic fixture. Preserved standalone and
actual A4-page baselines. Iterated the CeTZ source under explicit professor and
student critiques, regenerated the fixture and thesis, inspected color and
grayscale renders, and ran independent scientific and visual reviews. Rejected
a real-scene 3D version for this metric-specific lane because GT mesh, OBB,
camera history, and frusta introduce visibility and crop semantics already
owned by the calibrated candidate-geometry figure.

## Findings

- Point-to-mesh accuracy averages exact squared point-to-triangle distance over
  reconstructed points; mesh-to-point completeness averages the reverse exact
  distance over mesh faces.
- Equal-face completeness is not an area-weighted surface integral and is not
  invariant to retessellation.
- In the controlled fixture, planar support and five reconstruction points stay
  fixed. Point-to-mesh accuracy remains `0.00640 m^2`, while a left-weighted
  non-uniform tessellation changes mesh-to-point completeness from
  `0.03640 m^2` to `0.02284 m^2`.
- The left region contributes 32 of 40 equally weighted refined faces. The
  fixture generator now exports this count and the exact projected region
  outline so the figure cannot reconstruct projection geometry by hand.
- The accepted figure uses one solid point-to-triangle witness, one dashed
  triangle-to-point witness, direct population labels, a projected region
  boundary, and a controlled-conclusion strip. Its caption and alternative text
  state the synthetic mechanism role and exclude ASE-performance inference.

## Review Corrections

- Replaced the initial screen-space region rectangle with the fixture-exported
  projected quadrilateral and redrew its dashed outline above mesh faces.
- Replaced “only the face table changes” and “refined half” with the exact
  claims “only tessellation changes” and “left region: 32/40 equal-weight
  faces.”
- Exact scientific and visual re-reviews approve with zero P0--P2 findings.

## Commits

- [04d481b93bfac45487ea675abb6f76ef118dd3e1](https://github.com/JanDuchscherer104/ARIA-NBV/commit/04d481b93bfac45487ea675abb6f76ef118dd3e1)

## Verification

- PASS: fixture regenerated twice with byte-identical JSON.
- PASS: all 90 `aria_nbv/tests/rri_metrics` tests.
- PASS: Ruff check and format check for the fixture generator.
- PASS: `make thesis-pdf`, `make thesis-pdf-ci`,
  `make typst-authoring-contract`, and `make thesis-marker-contract`.
- PASS: 123-page A4 thesis; exact page 68 and standalone figure inspected in
  color and grayscale.
- PASS: independent scientific and professor/student visual re-reviews; zero
  P0--P2 findings.
- PASS: `git diff --check`.

## Canonical Owner Impact

The deterministic fixture generator owns the projected weighted-region outline
and count. The Typst figure owns the accepted visual explanation, while the
adjacent thesis section owns its semantic alternative text, caption, and
interpretive scope. No Python metric behavior or canonical equation changed.
