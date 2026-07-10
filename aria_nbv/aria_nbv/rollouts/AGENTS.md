---
scope: module
applies_to: aria_nbv/aria_nbv/rollouts/**
summary: Multi-step rollout records, rollout Zarr, and finite-candidate replay guidance.
---

# Rollout Boundary

Apply this file when working under `aria_nbv/aria_nbv/rollouts/`.

## Public Contracts
- Public package surface: `aria_nbv/aria_nbv/rollouts/__init__.py`
- Counterfactual transition replay and rollout policies: `counterfactuals.py`
- Target-cropped oracle rollout scoring: `target_counterfactuals.py`
- Compact rollout Zarr record and lineage sidecar: `trace.py`
- Standalone rollout replay store: `zarr_store.py`
- Rollout generation pipelines and CLI: `aria_nbv.oracle.pipelines`

## Boundary Rules
- `aria_nbv.rollouts` owns multi-step rollout records, rollout Zarr/Q stores,
  counterfactual transition replay, and the currently unsplit target-aware
  oracle rollout scorers. `aria_nbv.oracle.pipelines` owns rollout generation,
  shard execution, and the `nbv-build-rollouts` CLI.
- `aria_nbv.data_handling` remains the owner of raw snippets, `VinOracleBatch`,
  `VinOfflineDataset`, immutable VIN offline stores, and actor-visible target
  selection DTOs. Rollout generation consumes `VinOfflineSample` roots only;
  `VinOracleBatch` remains the one-step VIN training DTO.
- `aria_nbv.pose_generation` remains the owner of finite candidate pose
  sampling, validation, orientation, and candidate-table provenance. Rollout
  transitions, target-specific oracle scoring, rollout persistence, and replay
  schemas should not be exported from `pose_generation`.
- Do not mutate or version-bump the immutable VIN offline store to add
  multi-step replay data. Store rollout replay in standalone rollout artifacts
  with source-row lineage.
- Invalid candidates and invalid targets are hard-mask/reason-code cases, not
  low-RRI labels. `q_train_mask` must require explicit target-RRI supervision.

## Verification
- Run `ruff format` and `ruff check` on touched rollout files.
- Run `uv run pytest tests/rollouts` for record/Zarr/writer changes.
- Run `uv run pytest tests/data_handling/test_target_selection.py` when the
  generator consumes target-selector fields.
- Run Rerun/Streamlit tests when changing rollout reader arrays or launcher
  surfaces.
- Run `uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml --dry-run`
  for CLI/config wiring changes.

## Completion Criteria
- Public imports come from `aria_nbv.rollouts` for rollout record/store
  contracts, counterfactual rollout policies, and target-RRI rollout scorers.
- Generation callers import writer and shard symbols from
  `aria_nbv.oracle.pipelines` leaf modules.
- The standalone rollout store validates after writes.
- Docs or package guidance reflect any changed ownership boundary.
