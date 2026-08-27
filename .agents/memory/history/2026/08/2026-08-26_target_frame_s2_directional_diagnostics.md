---
id: 2026-08-26_target_frame_s2_directional_diagnostics
date: 2026-08-26
title: "Target-frame S2 directions and calibrated frustum support"
status: done
topics: [rollouts, streamlit, target-frame, s2, frustum, visibility]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - aria_nbv/aria_nbv/rollouts/s2_reporting.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/s2_directions.py
  - aria_nbv/aria_nbv/reporting/_rollouts.py
  - aria_nbv/aria_nbv/reporting/config.py
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
  - aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_geometry_diagnostics.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py
  - docs/typst/shared/symbols/spatial.typ
  - docs/typst/shared/equations/spatial.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-03-replay-stores-and-diagnostics.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 76d2a84b3bee132465f6cfb5252f0f5f69d00b23
repo_branch: "codex/s2-target-direction-spheres"
worktree_kind: linked
---

## Task
Add inspectable target-frame S² movement and camera-view histograms, then
extend them with calibrated selected-camera frustum footprints and explicit
support provenance on factual rollout paths.

## Method
The store-owned reducer transforms selected camera increments and local ``+Z``
axes from world into each target OBB frame. Movement uses the geometric-mean
OBB semi-axis scale before projection. For every calibrated selected view, it
tests front-facing points on the target-centred proxy sphere against the
persisted LUF half-pixel pinhole image rectangle. The rollout-owned Plotly
builder renders complete equal-solid-angle count surfaces with bounded
deterministic overlays carrying rollout-chain and acquisition-step provenance
for both Streamlit and immutable thesis reports.

## Findings
- `aria_nbv/aria_nbv/rollouts/inspection.py` owns target-frame reduction,
  equal-solid-angle bins, calibration joins, analytic rectangular-pinhole
  solid angle, proxy-surface coverage, explicit exclusions, and reservoirs.
- `rollouts/s2_reporting.py` owns the shared Plotly specification;
  `_stored_rollouts/s2_directions.py` owns the interactive scientific
  explanation. Both Q_H stored-rollout admission and Campaign Generation reuse
  the presentation after explicit full-store dispatch, while scientific
  reporting freezes the same Plotly payload for Typst.
- Q_H widget state is scoped to immutable store identity, and Campaign
  Generation admits only validator-returned current-plan shard paths.
- Colour preserves rollout-chain index `j`; marker symbol preserves persisted
  decision step `t`. Complete heat fields are never replaced by the bounded
  display overlay.
- The held-out `qh-s1-cfplus-heldout-iter10` shard yielded one sample, one
  snippet, one scene, one target, one rollout, five selected steps, five
  movement directions, five view directions, and five calibrated frusta with
  no missing calibration or geometry issues.
- The frozen 36 by 18-cell thesis pilot reports mean intrinsic FOV 2.489833 sr,
  mean per-view proxy support 16.8210%, and factual-view union support 31.1728%.
- The thesis labels this geometric potential visibility. It does not claim
  true target-mesh visibility because proxy-sphere shape error and scene
  occlusion are not resolved.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/690cedb325f52d93f78207b9b115b3b7c90f448b
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/8d8ea08930cecbcc266aa4011a873bb77b09dd47
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/72b93aa8e3ecc18f7f1c9b8cc8b29ac9be94693c
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/c86e4b4cdd9a9e9522e93abf6d441af7d9de8282
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/76d2a84b3bee132465f6cfb5252f0f5f69d00b23
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/c1a2180a360a4d181574f8b49d744ce4a5e86710
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/4b8832dffaa42dc6183183589022d0b0cd7716ec
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/965c0fd640db2a30ab74ce1674f204a0271cf6d1

## Verification
- Targeted Ruff check and `git diff --check`: passed.
- Reporting, rollout inspection, stored-rollout projection, geometry, and
  theory suites: 190 passed.
- Shared glossary and notation regeneration: 57 terms, 110 symbols, and 112
  equations validated.
- Development thesis compiled and all three generated S² figure pages were
  visually inspected.
- Targeted mypy remains informational because its imported package baseline
  reports pre-existing failures; newly changed lines were repaired and the
  focused runtime/test contracts pass.

## Canonical Owner Impact
Executable rollout inspection owns the numerical diagnostic; the rollout-owned
Plotly builder owns shared presentation; reporting owns immutable snapshot and
export; shared symbols/equations and the active method/data chapters own
notation and interpretation. The implementation remains an admission
diagnostic and does not promote S² memory into scorer state.
