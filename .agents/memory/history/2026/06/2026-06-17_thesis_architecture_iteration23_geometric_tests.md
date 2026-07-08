---
id: 2026-06-17_thesis_architecture_iteration23_geometric_tests
date: 2026-06-17
title: "Thesis Architecture Iteration 23 Geometric Tests"
status: done
topics: [thesis, architecture, geometry, invariance, q-h, tests]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/rl_planning.qmd
  - aria_nbv/tests
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 23 turns the planned geometric-invariance thesis section into a
testable contract. It separates coordinate gauges from physical signals:
candidate rows need permutation equivariance; local-frame pose features should
be stable under coordinate-origin and horizontal-frame changes; gravity, camera
frustum, invalidity, target support, and selected history remain meaningful
task signals. Exact equivariant modules are treated as ablations that must pass
synthetic transformation checks before receiving an equivariance claim.

## Evidence

- `docs/contents/theory/candidate_view_dependence.qmd` already owns the core
  set-model contract: candidate rows are an unordered finite set, required
  symmetry is `f(P X)=P f(X)`, and row-shuffle/mask tests are mandatory before
  trusting candidate-set gains.
- `docs/contents/theory/rl_planning.qmd` defines `Q_H` as one masked value per
  finite candidate and keeps invalidity as hard masks/reason codes.
- `.agents/memory/state/GOTCHAS.md` and `.agents/memory/state/DECISIONS.md`
  warn that pose frames, CW90, `PoseTW`, and `CameraTW` contracts are easy to
  misuse and block scale-up when wrong.
- The local QCNet/DeepSets/Set Transformer/GDL literature metadata supports
  query-centric relative encodings and candidate-set permutation tests.
- The SE(3)-Transformer source warns that fully rotation-invariant processing
  can lose performance on gravity-aligned object data and that up/gravity can
  be a useful symmetry-breaking signal.
- The EGNN source provides a lightweight exact-equivariance ablation based on
  relative distances, relative coordinate updates, and permutation-equivariant
  graph processing.
- The local `S^2`/spherical-harmonic work note frames second-moment directional
  memory as the thesis-safe baseline and spherical harmonics as the higher
  capacity ablation.

## Canonical Updates Needed

- Add a transformation/test matrix to the thesis method chapter: row shuffle,
  padded invalid rows, duplicate candidates, translation, yaw gauge changes,
  CW90/display isolation, target-local gauge, directional-memory rotation, and
  candidate-family stress.
- Add acceptance criteria to the evaluation chapter for each architecture stage:
  independent scorer, DeepSets, masked Set Transformer, QCNet-style RPE,
  directional memory, EGNN/SE(3) ablations, and point/sparse backbones.
- When a learned model exists, implement tests or fixtures for row-shuffle
  equivariance, mask isolation, duplicate-row stress, local-frame consistency,
  `S^2` second-moment rotation consistency, and declared exact-equivariance
  checks.
- Avoid thesis wording that says full `SE(3)` or `SO(3)` invariance is
  intrinsically better for ARIA-NBV; gravity/up, camera/frustum conventions,
  and selected-history order are physical signals.
