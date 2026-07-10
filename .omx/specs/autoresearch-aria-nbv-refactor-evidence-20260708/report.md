# ARIA-NBV Refactor Evidence And Suggestions

Date: 2026-07-08

Scope: read-only architecture research. This report is grounded in recent
persisted plans plus live source inspection. It does not propose VIN,
`rri_metrics`, or Lightning implementation work.

## Executive Synthesis

The freshest planning line is the July 2 PR15 package-boundary work. It approved
only the counterfactual rollout ownership move before merge, and explicitly
deferred broad `data_handling`, app, RL, target-descriptor, target-conditioned
scoring, Q_H, and scene-memory work. That plan was implemented in the separate
PR15 cleanup worktree as commit `f6d5bf9`.

For the next architecture pass, the strongest final ownership rule is:

1. `rri_metrics` owns pure metric primitives such as `OracleRRI.score`.
2. `pipelines` owns end-to-end Oracle RRI orchestration: candidate generation,
   rendering, backprojection, root/current eval-point construction, scene-vs-
   target eval-region policy, and labeler/scorer config surfaces.
3. `rollouts` owns replay DTOs, selected-transition traces, rollout stores, and
   readers/writers. It should consume Oracle RRI pipeline objects, not own them.
4. `data_handling` owns raw snippets, immutable offline store readers/writers,
   VIN source adapters, and target selection/source DTOs until a real target
   package is introduced.

That rule means the July 2 rollout move is useful as an intermediate cleanup,
but `CounterfactualTargetOracleRriScorer` should not remain the long-term owner
of target-RRI orchestration inside `rollouts/target_counterfactuals.py` if the
new rule is "all Oracle RRI pipelines live under `aria_nbv.pipelines`".

## Recency-Weighted Prior Evidence

The July 2 handoff selects "Option A: counterfactuals-first cleanup" and
summarizes it as moving `pose_generation.counterfactuals` and
`pose_generation.target_counterfactuals` into `aria_nbv.rollouts`, while
deferring RL archival, broad app-panel helper extraction, broad `data_handling`
or utils restructuring, target descriptors, target-conditioned scoring, Q_H,
scene memory, and online RL core
(`.omx/plans/aria-nbv-package-boundary-cleanup-handoff-20260702T162044Z.json:19-28`).

The same handoff merged Claude findings but constrained them: keep the immediate
counterfactual move and record broader findings as sequenced follow-ups, with
"do not perform broad data_handling/utils/app restructuring" as an explicit
no-new-feature boundary
(`.omx/plans/aria-nbv-package-boundary-cleanup-handoff-20260702T162044Z.json:79-90`).

The ranked Claude finding for Oracle RRI remains open: the target scorer
duplicates the scene scorer, and a third path exists in
`pipelines/oracle_rri_labeler.py`; the recommended repair is one scorer skeleton
parameterized by an eval-region policy
(`.omx/plans/aria-nbv-package-boundary-cleanup-handoff-20260702T162044Z.json:106-115`).

The multi-phase `.omc` plan is more explicit about the desired follow-up:
Phase 4 extracts `RolloutRriScorerBase`, common config fields, shared
root-eval caching, and an eval-region policy, while `pipelines/oracle_rri_labeler.py`
stays as the offline-labeling lifecycle and consumes shared helpers
(`.omc/plans/plan-aria-nbv-refactor-20260702.md:75-97`).

The same `.omc` plan identifies `_target_selection.py` as a later split:
DTOs/enums, selector/sampler classes, and OBB/scoring helpers should become
focused private modules while preserving `data_handling.__init__` re-exports
(`.omc/plans/plan-aria-nbv-refactor-20260702.md:175-191`).

The slop audit independently reports the same pressure points: twin oracle-RRI
scorers, `zarr_store.py` table boilerplate, parallel rollout read stacks, `rl/`
as post-M6 but wired into app config, and `_target_selection.py` as a high-churn
1,389-line mixed file
(`.agents/memory/history/2026/07/2026-07-02_aria_nbv_slop_audit.md:35-76`).

## Live Code Evidence

### Oracle RRI Is Scattered

`aria_nbv.pipelines` currently contains only `oracle_rri_labeler.py`. It owns a
one-step scene-labeling flow: generate candidates, render depths, backproject
candidate point clouds, and call `OracleRRI.score`
(`aria_nbv/aria_nbv/pipelines/oracle_rri_labeler.py:80-149`).

The pure metric primitive lives in `rri_metrics/oracle_rri.py`. It accepts
`points_t`, `points_q`, `lengths_q`, GT mesh tensors, and an AABB `extend`, crops
the mesh, fuses point clouds, and computes RRI. It also still exposes
`score_batch` as an alias
(`aria_nbv/aria_nbv/rri_metrics/oracle_rri.py:72-151`).

The scene counterfactual scorer currently owns render/backproject/current-eval
construction and calls `OracleRRI.score`
(`aria_nbv/aria_nbv/pose_generation/counterfactuals.py:700-848` in the main
checkout; moved to `rollouts/counterfactuals.py` in the PR15 cleanup worktree).

The target counterfactual scorer owns target GT OBB resolution, target mesh crop,
target current/candidate point crops, target and optional scene RRI calls, and
target eval crop payloads
(`aria_nbv/aria_nbv/pose_generation/target_counterfactuals.py:73-390` in the
main checkout; moved to `rollouts/target_counterfactuals.py` in the PR15 cleanup
worktree).

Conclusion: the previous "move to rollouts" fixed candidate-vs-replay ownership,
but it did not unify Oracle RRI orchestration. If the desired owner is
`pipelines`, the next move should be pipeline ownership plus deduplication, not a
third thin relocation.

### `data_handling` Has One High-Value Split, Not A Whole-Package Rewrite

`data_handling.__init__` advertises the correct broad contract: raw ASE/EFM
views, VIN one-step batches, strict immutable offline stores, oracle target-task
sampling, and actor-visible target selection. It also explicitly states
actor/oracle separation and hard invalidity
(`aria_nbv/aria_nbv/data_handling/__init__.py:1-18`).

The root package re-exports target selection DTOs and configs from
`_target_selection.py`
(`aria_nbv/aria_nbv/data_handling/__init__.py:68-85`, `:94-162`).

`_target_selection.py` mixes:

- target enums and actor-visible DTOs near lines 56-199;
- oracle target-task DTOs near lines 200-330;
- `TargetSelectorConfig`, `OracleTargetTaskSamplerConfig`,
  `OracleTargetTaskSampler`, and `ActorVisibleTargetSelector` through roughly
  lines 348-1038;
- OBB/world-transform/support/visibility/IoU/scoring helpers from line 1040
  through the end.

Conclusion: restructure this file, not all of `data_handling`. Keep the public
root stable and split private owners.

### `rl/` Is Non-Core, But Not Unused

`aria_nbv/aria_nbv/rl` is small, 585 LOC total, but it is active:

- `app/config.py` imports `CounterfactualPPOConfig` and
  `CounterfactualRLEnvConfig` and includes them in `RlPageConfig`
  (`aria_nbv/aria_nbv/app/config.py:9-12`, `:37-72`).
- `app/panels/rl.py` imports `CounterfactualRLEnv` and its config, and contains
  SB3 checkpoint playback helpers
  (`aria_nbv/aria_nbv/app/panels/rl.py:15-24`, `:120-128`).
- `tests/rl/test_counterfactual_env.py` imports the public `aria_nbv.rl` root
  and runs Gymnasium/SB3 smoke coverage when dependencies are installed
  (`aria_nbv/tests/rl/test_counterfactual_env.py:12-30`, `:138-152`).
- `tests/app/panels/test_rl_panel.py` and
  `tests/test_config_field_constraints.py` also import the RL config surfaces
  (`aria_nbv/tests/app/panels/test_rl_panel.py:9-13`,
  `aria_nbv/tests/test_config_field_constraints.py:12-34`).

Conclusion: `rl/` is not thesis-core and should be quarantined or archived, but
it is not dead code. Archiving it requires removing or archiving app config,
panel, and test surfaces in the same package.

## Recommended Workpackages

### 1. Oracle RRI Pipeline Ownership And Scorer Unification

Target owner:

```text
aria_nbv/aria_nbv/pipelines/
  oracle_rri_labeler.py          # existing one-step scene labeler
  rollout_oracle_rri.py          # scene and target rollout RRI scorers
  oracle_rri_regions.py          # optional: scene extent vs GT-OBB policy
```

Keep:

- `aria_nbv.rri_metrics.oracle_rri` as the pure metric primitive.
- `aria_nbv.rollouts` as replay/trace/store owner.
- `aria_nbv.pose_generation` as candidate table generation.

Execution:

1. Add regression tests before moving logic: scene scorer and target scorer
   should produce identical outputs before/after on shared synthetic fixtures.
2. Move scorer configs/classes from `rollouts` into `pipelines` if the PR15
   cleanup worktree is the base. If working from main, move from
   `pose_generation` directly to `pipelines`.
3. Extract the shared base for renderer setup, oracle setup, root-eval caching,
   `_current_eval_points`, reward-mode postprocessing, and common config fields.
4. Represent the difference as an eval-region policy:
   `SceneExtentPolicy` uses candidate occupancy bounds; `TargetObbPolicy`
   resolves matched GT OBB, crops mesh/current/candidate points, and raises
   target-invalid errors.
5. Let `rollouts/dataset_writer.py` consume the pipeline scorer, and let
   `rollouts/trace.py`/`zarr_store.py` remain DTO/store consumers only.

Validation:

- `cd aria_nbv && uv run pytest tests/rollouts/test_counterfactuals.py`
- `cd aria_nbv && uv run pytest tests/rollouts`
- `cd aria_nbv && uv run pytest tests/rri_metrics`
- `cd aria_nbv && uv run pytest tests/integration/test_oracle_rri_labeler_real_data.py`
- `cd aria_nbv && uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml --dry-run`
- `rg -n "Counterfactual.*OracleRriScorer|target_counterfactuals|oracle_rri_labeler" aria_nbv/aria_nbv aria_nbv/tests`

Risk: this can silently change labels. Do not combine it with metric primitive
rewrites, crop-policy changes, target descriptors, or Q_H implementation.

### 2. Focused `data_handling._target_selection` Split

Do this after PR15 is green and after the Oracle RRI pipeline owner is settled.
Do not create a public `targets/` package yet unless the next target-conditioned
PR actually needs it.

Suggested private split:

```text
aria_nbv/aria_nbv/data_handling/
  _target_types.py          # enums, invalid reason codes, DTO rows/results
  _target_sampler.py        # OracleTargetTaskSampler + config
  _target_selection.py      # ActorVisibleTargetSelector + config
  _target_obb_geometry.py   # OBB/world/support/visibility/IoU helpers
```

Keep all public imports stable through `data_handling.__init__`.

Validation:

- `cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py`
- `cd aria_nbv && uv run pytest tests/data_handling/test_public_api_contract.py`
- `cd aria_nbv && uv run ruff check aria_nbv/data_handling tests/data_handling`
- `rg -n "from aria_nbv.data_handling._target" aria_nbv/aria_nbv aria_nbv/tests`

Risk: splitting too broadly can create import cycles with `_offline_dataset`,
`vin_oracle_types`, and `vin.types`. Keep helpers private and avoid changing
root exports.

### 3. RL Quarantine Or Archive

The evidence supports "not current thesis core"; it does not support "unused".
Treat this as an intentional product/API contraction.

Two viable choices:

Option A, archive:

```text
.agents/archive/aria_nbv/rl/
  counterfactual_env.py
  __init__.py
  tests/test_counterfactual_env.py
  app_panel_rl.py
```

Then remove active imports from:

- `aria_nbv/aria_nbv/app/config.py`
- `aria_nbv/aria_nbv/app/panels/__init__.py`
- `aria_nbv/aria_nbv/app/panels/rl.py`
- `aria_nbv/tests/app/panels/test_rl_panel.py`
- `aria_nbv/tests/test_config_field_constraints.py`

Option B, quarantine in-package:

```text
aria_nbv/aria_nbv/experimental/rl/
```

This keeps runnable code but removes it from the active root API and app config.
Use this only if preserving local playback is valuable.

Validation:

- `rg -n "aria_nbv\\.rl|CounterfactualRLEnv|CounterfactualPPO|render_rl_page|RlPageConfig" aria_nbv/aria_nbv aria_nbv/tests`
- `cd aria_nbv && uv run pytest tests/app tests/test_config_field_constraints.py`
- `cd aria_nbv && uv run pytest tests/data_handling/test_public_api_contract.py`

Risk: deleting `rl/` alone will break app and config tests. Remove the page and
config references in the same commit, or keep the package active.

## Suggested Ordering

Before PR15 merge:

1. Do not add new refactor packages unless PR15 is already green.
2. Keep the committed rollout-boundary move as the narrow pre-merge cleanup.
3. If necessary, trim review-noise docs/agent artifacts from that commit, but do
   not start data-handling, RRI unification, or RL archival in the same diff.

After PR15 merge:

1. Oracle RRI pipeline ownership and scorer unification under `pipelines`.
2. RL archive/quarantine as a separate API contraction.
3. Focused `_target_selection.py` split with root re-exports preserved.
4. Zarr schema/read-model/geometry cleanups only after those owner seams are
   settled.

## Stop Lines

Do not implement target descriptors, target-conditioned scoring, Q_H, scene
memory, new online RL baselines, or broad `data_handling` package moves in these
cleanup packages. Each package should be independently reviewable and should
shrink or clarify ownership without changing scientific semantics.
