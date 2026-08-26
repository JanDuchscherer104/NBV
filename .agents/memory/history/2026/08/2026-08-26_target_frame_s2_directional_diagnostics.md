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
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/s2_directions.py
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
  - aria_nbv/aria_nbv/oracle/pipelines/admission_evidence.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_geometry_diagnostics.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py
  - docs/typst/shared/symbols/spatial.typ
  - docs/typst/shared/equations/spatial.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 076789a49b375c2c86962c8151b404de7caacd6e
repo_branch: "codex/s2-target-direction-spheres"
worktree_kind: linked
---

## Task
Add inspectable target-frame S² movement and camera-view histograms, then
extend them with calibrated selected-camera frustum footprints and explicit
support provenance on factual rollout paths.

## Method
The store-owned reducer transforms selected camera increments and local ``+Z``
axes from world into each target OBB frame. Movement uses the
volume-equivalent OBB radius before projection. For every calibrated selected
view, it tests front-facing points on the target-centred proxy sphere against
the persisted LUF pinhole image rectangle. Streamlit renders complete
equal-solid-angle count surfaces with bounded deterministic overlays carrying
rollout-chain and acquisition-step provenance.

## Findings
- `aria_nbv/aria_nbv/rollouts/inspection.py` owns target-frame reduction,
  equal-solid-angle bins, calibration joins, analytic rectangular-pinhole
  solid angle, proxy-surface coverage, explicit exclusions, and reservoirs.
- `_stored_rollouts/s2_directions.py` owns the shared Plotly and scientific
  explanation surface. Both Q_H stored-rollout admission and Campaign
  Generation reuse it after explicit full-store dispatch.
- Colour preserves rollout-chain index `j`; marker symbol preserves persisted
  decision step `t`. Complete heat fields are never replaced by the bounded
  display overlay.
- The held-out `qh-s1-cfplus-heldout-iter10` shard yielded one sample, one
  snippet, one scene, one target, one rollout, five selected steps, five
  movement directions, five view directions, and five calibrated frusta with
  no missing calibration or geometry issues.
- At 72 by 36 equal-area cells its mean intrinsic FOV was 2.489985 sr, mean
  per-view proxy support was 16.6049%, and factual-view union support was
  31.2114%.
- The thesis labels this geometric potential visibility. It does not claim
  true target-mesh visibility because proxy-sphere shape error and scene
  occlusion are not resolved.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/921a3b9cfb55b90fa52da6e4b289ca924540319a
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/076789a49b375c2c86962c8151b404de7caacd6e

## Verification
- Targeted Ruff check and `git diff --check`: passed.
- Rollout reducer, presentation, campaign page, and admission evidence suites:
  192 passed.
- Stored-rollout projection-laziness suite: 42 passed.
- Shared glossary and notation regeneration: 57 terms, 110 symbols, and 112
  equations validated.
- Development thesis compiled and the two affected pages were visually
  inspected.
- Targeted mypy remains informational because its imported package baseline
  reports pre-existing failures; newly changed lines were repaired and the
  focused runtime/test contracts pass.

## Canonical Owner Impact
Executable rollout inspection owns the numerical diagnostic; the shared
Streamlit renderer owns presentation; shared symbols/equations and the active
method chapter own notation and interpretation. The implementation remains an
admission diagnostic and does not promote S² memory into scorer state.
