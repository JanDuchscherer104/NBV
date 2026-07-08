---
id: 2026-07-02_aria_nbv_slop_audit
date: 2026-07-02
title: "aria_nbv refactor / AI-slop audit (reviewer-only pass)"
status: done
topics: [aria_nbv, refactor, simplification, vin, rollouts, pose_generation]
confidence: high
canonical_updates_needed: []
---

## Task

Reviewer-only ai-slop-cleaner pass over `aria_nbv/` (~93k LOC, 309 files):
identify the biggest refactor/simplification opportunities to prepare for the
multi-step target-conditioned NBV model. No code was changed.

## Method

Size/outline scans (`wc -l`, `grep` for class/def), import-graph greps for
dead surfaces, git churn over the last 30 commits, and targeted reads of
`model_v3.py`, `lit_module.py`, `counterfactuals.py`,
`target_counterfactuals.py`, `zarr_store.py`.

## Ranked findings

1. **`vin/experimental/` (~5.5k LOC) is a dependency trap, not an experiment.**
   `experimental/model.py` (1210 LOC) has zero importers; `model_v1_SH.py`
   (627) is only kept alive by `tests/test_config_field_constraints.py:36`.
   Meanwhile load-bearing v3-path code lives there: `VinForwardDiagnostics`
   (`experimental/types.py`) is imported by `app/state_types.py`,
   `app/panels/vin_utils.py`, diag tabs; `experimental/plotting.py` is imported
   by `lightning/lit_module.py:49` and 5 diag tabs; `model_v2.FIELD_CHANNELS_V2`
   by the summary tab. Delete dead models, promote the used pieces into `vin/`.

2. **Twin oracle-RRI scorers are copy-paste.** `CounterfactualOracleRriScorer`
   (`pose_generation/counterfactuals.py:700-848`) vs
   `CounterfactualTargetOracleRriScorer` (`target_counterfactuals.py:73-395`):
   ~12 identical config fields, duplicated root-eval caching
   (`_root_eval_for`/`_current_eval_points`), same render→backproject→fuse→score
   skeleton. A third labeler lives in `pipelines/oracle_rri_labeler.py`.
   Unify as one scorer parameterized by an eval-region/crop policy.

3. **`rollouts/zarr_store.py` (3056 LOC) hand-rolls columnar tables.**
   `_TableSchema` exists but each table (targets, candidates, diagnostics,
   selected-depth, eval-crops) has bespoke `_empty_*`/`_append_*`/
   `_rows_to_numpy_*`/`_read_*`/`_write_*` functions; Q_H is derived three
   times (write `_build_q_h_arrays`, read `q_h_view`, validator re-derive).
   Schema-driven generic table would collapse >1k LOC and make adding
   multi-step fields a one-line schema change.

4. **Frustum/CW90 geometry duplicated across ≥6 modules.** Frustum corners:
   `utils/data_plotting.py:99`, `rerun_inspector/_frusta.py` (3 fns),
   `vin/vin_utils.py:288,350`, `vin/_model_mixins.py:68`,
   `rendering/plotting.py:237`. CW90: `utils/frames.py:192` (canonical),
   `vin/_plotting_common.py:209`, `rerun_inspector/_frusta.py:175,385`,
   `utils/data_plotting.py:1090`, plus the implicit
   `p3d_cameras.cw90_corrected` getattr-flag protocol in `model_v3.py:1276`.

5. **~7.2k LOC of parallel rollout read-side diagnostics**:
   `rollouts/inspection.py` (1410), `rerun_inspector/_rollout_zarr.py` (1866),
   `app/panels/stored_rollouts.py` (1729), `app/panels/counterfactual_rollouts.py`
   (2030) all re-summarize `RolloutZarrStoreReader` rows independently.

6. **God methods on the training path**: `VinModelV3._forward_impl`
   (model_v3.py:1206-1540, ~334 LOC; also lazy backbone init + `self.to(device)`
   side effect inside forward) and `VinLightningModule._step`
   (lit_module.py:354-639, ~285 LOC mixing loss, masking, coverage weights,
   CORAL variants, logging); lit_module also owns plotting/summarize.

7. **Misc**: 101 `except Exception` sites (mostly app panels +
   `rollouts/inspection.py` with 13) vs the no-silent-failure rule; `rl/`
   (585 LOC, post-M6 per roadmap) wired into `app/config.py`; 72 config
   classes each re-declaring `target_type`; 7 hand-written DTO `.to(device)`
   methods; duplicate `utils/summary.py` vs `utils/rich_summary.py`;
   `_target_selection.py` (1389 LOC, highest churn: 11 of last 30 commits)
   mixes DTOs, two selectors, and ~30 module-level geometry helpers.

## Outcome

Findings reported to the user with a suggested safest-first sequencing
(dead-code deletion → scorer unification → zarr schema table → geometry
consolidation). No edits performed; behavior unchanged.

## Update 2026-07-02 (reconciled with `codex/vin-cleanup-pr15-integration`)

Branch (PR #15 integration, +11.8k/-3.9k vs merge-base `10487ba`) resolves
findings 1 and much of 6 inside `vin/`: `experimental/` dissolved
(`model.py`/`model_v1_SH.py` deleted, types → `vin/types/`, encoders →
`vin/encoders/`, model_v2 → `vin/models/v2.py`), `model_v3` →
`vin/models/scene_myopic.py` (1636→1057) with extracted `vin/geometry/`,
`vin/modules/`, `vin/diagnostics/`, `vin/feature_bank/`; adds
`CandidateScorer` Protocol + `target_myopic`/`target_finite_horizon`
scaffolds. Constraints for the bounded pass live in
`.omx/context/aria-nbv-package-boundaries-20260702T162044Z.md`
(no Q_H impl, no broad data_handling/utils/app restructuring; first move =
relocate counterfactual rollout contracts from `pose_generation` to
`rollouts`; RL package is active, keep).

Still open after the branch: twin counterfactual RRI scorers,
`zarr_store.py` table boilerplate, cross-package frustum/CW90 duplication
(`vin/geometry/frustum.py` covers vin only), four rollout read-side stacks,
`lit_module._step` (grew to ~348 lines), `_target_selection.py` split.
New on-branch observations: `rri_metrics/torch_rollout_metrics.py`
(880 LOC torchmetrics wrappers) is imported only by its own test;
`vin/diagnostics/experimental_plotting.py` keeps the misleading name;
v2 lineage (~2k LOC: models/v2.py, _v2_semidense.py, summarize_v2.py)
retained pending a thesis-relevance decision.
