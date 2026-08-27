---
id: 2026-08-27_candidate_view_diagnostics_persistence
date: 2026-08-27
title: "Candidate view diagnostics persistence"
status: done
topics: [candidate-generation, rollout-zarr, streamlit, view-jitter, target-framing]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/candidate_generation.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py
  - aria_nbv/aria_nbv/rollouts/zarr_contract.md
codex_thread: codex://threads/01a03a5c-ff92-7e03-8cd3-fde05269a56f
repo_object_format: sha1
repo_head: 55235a64a934819c2b42e4b0944fe496e4798905
repo_branch: "codex/candidate-scaleup-autoresearch"
worktree_kind: linked
---

## Task

Make candidate view realism inspectable before larger-scale rollout generation without changing candidate selection, oracle labels, or the nonzero seminar-jitter invariant.

## Method

Persisted the generator's full-shell view-jitter tensors and added actor-visible target-centre projection diagnostics through the exact `CameraTW` model. The optional Zarr bundle remains absent-but-valid for legacy stores. Inspection reducers and Streamlit plots expose measured framing separately from unavailable scene line of sight.

## Findings

- `aria_nbv/aria_nbv/pose_generation/candidate_generation.py` now measures target-centre angular error, signed pixel margin, and exact calibration in-FOV status for every family that receives actor-visible target context.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` preserves per-candidate bounded/unbounded jitter semantics and the target-framing bundle while accepting older stores that contain none of the optional arrays.
- `aria_nbv/aria_nbv/rollouts/inspection.py` keeps missing optical or visibility evidence explicit and never substitutes line of sight from target distance or in-FOV status.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py` plots bounded jitter with dotted configured envelopes; uncapped spherical rows use fixed yaw `[-180, 180]` and pitch `[-90, 90]` axes with no rectangle.

## Commits

- [55235a64a934819c2b42e4b0944fe496e4798905](https://github.com/JanDuchscherer104/ARIA-NBV/commit/55235a64a934819c2b42e4b0944fe496e4798905)

## Verification

- `pytest tests/pose_generation/test_candidate_mixture.py tests/rollouts/test_zarr_store.py tests/rollouts/test_inspection.py tests/app/panels/test_stored_rollouts_candidate_choice.py -q`: 189 passed.
- Targeted Ruff check passed for all changed Python and test files.
- Targeted mypy passed for `rollouts/zarr_store.py`, `rollouts/inspection.py`, and the stored-rollout panel. The pose-generation files retain pre-existing package typing debt outside this change.

## Canonical Owner Impact

Current truth is updated in the Python, Zarr-contract, test, and Streamlit owners listed above. No further canonical update is required for this workpackage.
