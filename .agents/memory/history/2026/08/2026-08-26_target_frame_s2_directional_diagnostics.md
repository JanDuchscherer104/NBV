---
id: 2026-08-26_target_frame_s2_directional_diagnostics
date: 2026-08-26
title: "Target-frame S2 directional diagnostics"
status: done
topics: [rollouts, streamlit, target-frame, s2]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/qh_admission.py
  - aria_nbv/tests/rollouts/test_inspection.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_geometry_diagnostics.py
  - aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 01d50b74bfaf2e56341a6909cec185d97368bf39
repo_branch: "codex/s2-target-direction-spheres"
worktree_kind: linked
---

## Task
Add inspectable S² movement and camera-view directional histograms for factual
selected rollout paths, expressed in target object coordinates.

## Method
The store-owned reducer transforms selected camera increments and local ``+Z``
axes from world into each target OBB frame. Movement uses the geometric-mean
OBB characteristic length before projection. Streamlit renders complete
equal-solid-angle count surfaces with bounded deterministic vector overlays.

## Findings
- `aria_nbv/aria_nbv/rollouts/inspection.py` owns target-frame S² reduction,
  explicit exclusions, geometric-mean OBB normalization, equal-solid-angle
  bins, and reservoir samples.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py` caches the
  immutable-store projection; `qh_admission.py` owns explicit dispatch, Plotly
  rendering, and operator explanation.
- The real held-out `qh-s1-cfplus-heldout-iter10` shard yielded five movement
  and five view directions with no exclusions; each surface retained a
  `surface` heat map and `scatter3d` projection overlay.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/01d50b74bfaf2e56341a6909cec185d97368bf39

## Verification
- Targeted Ruff format/check: passed.
- Target-frame reducer and figure tests: passed.
- Stored-rollout panel and laziness suite: 51 passed.
- Targeted mypy passes for the new Streamlit/session owners. The existing
  inspection-module mypy baseline remains 20 unrelated errors.

## Canonical Owner Impact
The executable rollout-inspection and Streamlit panel owners now define this
diagnostic. No thesis, notation, configuration, or guidance owner changes are
required because S² memory remains planned rather than implemented model state.
