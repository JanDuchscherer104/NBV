---
scope: module
applies_to: aria_nbv/aria_nbv/rollouts/**
summary: Multi-step rollout records, rollout Zarr, and finite-candidate replay guidance.
---

# Rollout Boundary

Apply this file when working under `aria_nbv/aria_nbv/rollouts/`.

## Public Contracts
- Public package surface: `aria_nbv/aria_nbv/rollouts/__init__.py`
- Counterfactual transition replay, score contracts, and rollout policies: `replay/`
- Scene/target Oracle scoring: `aria_nbv.oracle.scene_rri` and `aria_nbv.oracle.target_rri`
- Compact rollout Zarr record and lineage sidecar: `trace.py`
- Standalone rollout replay store: `zarr_store.py`
- Shared typed store interpretation for read-side adapters: `read_model.py`
- Operational replay/store checks: `audits.py`
- Inventory and presentation-ready audit summaries: `inspection.py`
- Rollout generation pipelines and CLI: `aria_nbv.oracle.pipelines`

## Boundary Rules
- `aria_nbv.rollouts` owns multi-step rollout records, rollout Zarr/Q stores,
  and counterfactual transition replay. Scene and
  target scoring live in `aria_nbv.oracle`.
  Oracle-to-replay adaptation lives only at pipeline or UI composition edges.
  `aria_nbv.oracle.pipelines` owns rollout generation,
  shard execution, and the `nbv-build-rollouts` CLI.
- `aria_nbv.data_handling` owns raw snippets, `VinOracleBatch`,
  `VinOfflineDataset`, and immutable VIN offline stores. `aria_nbv.targets`
  owns actor-safe target instructions; `aria_nbv.oracle` owns privileged
  target-task selection. Rollout generation consumes `VinOfflineSample` roots
  only; `VinOracleBatch` remains the one-step VIN training DTO.
- `aria_nbv.pose_generation` remains the owner of finite candidate pose
  sampling, validation, orientation, and candidate-table provenance. Rollout
  transitions, target-specific oracle scoring, rollout persistence, and replay
  schemas should not be exported from `pose_generation`.
- Do not mutate or version-bump the immutable VIN offline store to add
  multi-step replay data. Store rollout replay in standalone rollout artifacts
  with source-row lineage.
- Invalid candidates and invalid targets are hard-mask/reason-code cases, not
  low-RRI labels. `q_train_mask` must require explicit target-RRI supervision.
- Keep `read_model.py` presentation-free. Streamlit and Rerun own their chart,
  entity, color, transform, command, and failure-policy DTOs locally.
- The package root is an exact eight-symbol allowlist. Import codecs,
  manifests, policies, diagnostics, and read-model records from their leaf
  owners; do not add compatibility re-exports.

## Verification
- Run `ruff format` and `ruff check` on touched rollout files.
- Run `uv run pytest tests/rollouts` for record/Zarr/writer changes.
- Run `uv run pytest tests/oracle/test_target_selection.py` when the generator
  consumes Oracle target-task fields.
- Run Rerun/Streamlit tests when changing rollout reader arrays or launcher
  surfaces.
- Run `uv run nbv-build-rollouts --config-path ../.configs/generation/rollouts/smoke/build_rollouts_v1_smoke.toml --dry-run`
  for CLI/config wiring changes.

## Completion Criteria
- Stable replay entry points use `aria_nbv.rollouts`; specialized contracts use
  their owning leaf modules.
- Generation callers import writer and shard symbols from
  `aria_nbv.oracle.pipelines` leaf modules.
- The standalone rollout store validates after writes.
- Docs or package guidance reflect any changed ownership boundary.
