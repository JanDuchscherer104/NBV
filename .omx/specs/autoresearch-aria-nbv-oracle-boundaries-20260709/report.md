# ARIA-NBV Oracle / Metrics / Rollouts Architecture Proposal

Created: 2026-07-09  
Status: revised after independent architect/code-review feedback  
Scope: planning/review only; no package source code edited.

## Executive Decision

Create `aria_nbv.oracle`, but keep it narrow by splitting it into two explicit zones:

- `aria_nbv.oracle.scoring`: oracle evidence preparation and scene/target RRI label production.
- `aria_nbv.oracle.pipelines`: thin executable composition for oracle-label data generation.

`oracle` must not own metric formulas, replay/storage DTOs, target-source rows, rollout read models, Streamlit inspection, or VIN training. Its package root should export only the stable scorer/config/label-field API and should not barrel-export pipeline entrypoints.

The coherent split is:

- `data_handling.targets`: source rows, actor-visible target selection, GT target-task sampling, and target identity/audit DTOs.
- `rri_metrics`: pure metric math, differentiable gain/return transforms, objective helpers, TorchMetric adapters, and reporting/table reducers.
- `oracle.scoring`: evidence preparation, scene/target RRI label scoring, target crop policy, and canonical label-field semantics.
- `oracle.pipelines`: command-facing oracle-label data generation that composes data handling, candidate generation, oracle scoring, and rollout storage.
- `rollouts`: counterfactual replay state, selection policies, finite-candidate transition records, Zarr storage, derived replay views, and inspection/read-side summaries.

This is a locality rule: changing target-RRI label semantics should not require editing `rollouts`; changing discounted return math should not require editing `oracle`; changing target-source eligibility should not require editing either.

## Supersession Note

An earlier plan warned that top-level `oracle` could become premature and that current data-generation should remain in `aria_nbv.pipelines`. The current user requirement supersedes that: the project should not maintain the old top-level `aria_nbv.pipelines` package. The revised design preserves the warning by making `oracle.pipelines` a thin composition subpackage with no root exports and no formula/storage ownership.

## Evidence From Current Code

- `rollouts/counterfactuals.py` mixes replay DTOs, selection/generator logic, reward helpers, and scene Oracle-RRI scoring. Reward helpers are at lines 120-159, replay DTOs at 288-380, and `CounterfactualOracleRriScorer` at 702-850.
- `rollouts/target_counterfactuals.py` owns target Oracle-RRI label semantics, target crop policy, invalidity, scene diagnostic scoring, and target OBB crop helpers. The module contract is at lines 1-19, constants/config/scorer begin at 62-153, scoring begins at 188, and crop helpers are at 396-465.
- `rri_metrics/oracle/evidence.py` already owns root/current eval point-cloud construction and source semantics: `RriEvaluationPointCloudSource`, `RriRewardMode`, `RootEvalPointCloud`, and `build_root_eval_pointcloud` are at lines 24-129.
- `rri_metrics/oracle/scorer.py` owns `OracleRRI`, but it is semantically an oracle label scorer using point-mesh primitives, not an ordinary metric reducer. See lines 40-81.
- `pipelines/oracle_rri_labeler.py` is already an oracle label pipeline: it generates candidates, renders depths, backprojects point clouds, and calls `OracleRRI.score` at lines 80-157.
- `rollouts/dataset_writer.py`, `rollouts/shards.py`, `rollouts/shard_manifest.py`, and `rollouts/cli.py` implement oracle rollout data generation. Writer configuration composes target selection, target scoring, candidate mixture, selected-depth retention, and rollout store at `dataset_writer.py` lines 268-326.
- `data_handling/_target_selection.py` names the conceptual split in its docstring: `OracleTargetTaskSampler` builds GT target-task pools, while `ActorVisibleTargetSelector` handles actor-visible V1 selection. See lines 1-19.
- `data_handling/_target_selection.py` also proves why `data_handling` still has a role: `TargetCandidateRow` is a source/selection DTO at lines 93-147, `OracleTargetTaskRow` is a target-task DTO at lines 209-255, and `target_gt_obb_world` resolves a selected row back to source GT OBBs at lines 1052-1078.
- `rri_metrics/metrics/multi_step.py` mixes core differentiable transforms with diagnostics. Core return/gain functions are at lines 138-240; diagnostic ranking/provenance/path/invalidity helpers are at lines 299-760.
- `rri_metrics/metrics/multi_step_tables.py` duplicates scalar endpoint/return formulas for mapping rows, including `endpoint_target_gain`, `endpoint_log_gain`, and `finite_horizon_target_return` at lines 65-130.
- `rollouts/zarr_store.py` stores `target_root_gain` as the default Q_H reward (`Q_H_REWARD_METRIC` at lines 71-75), derives `q_h/` arrays from stored candidate fields at lines 2534-2603, and must remain a replay/storage owner rather than a label-formula owner.

Graphify query evidence also surfaced the same overlap cluster: `target_counterfactuals.py`, `counterfactuals.py`, `oracle_rri_labeler.py`, `dataset_writer.py`, `zarr_store.py`, `rri_metrics/metrics`, and `_target_selection.py` sit in the same import neighborhood around rollout labels, endpoint gains, storage, and target selection.

## Single-Owner Matrix

| Concept | Single Owner | Consumers | Explicit Non-Owners |
| --- | --- | --- | --- |
| Point-mesh distance primitives | `rri_metrics.point_mesh` | `oracle.scoring.scene_rri`, `oracle.scoring.target_rri`, tests, diagnostics | `oracle`, `rollouts`, `data_handling` |
| RRI metric result DTO | `rri_metrics.rri.RriResult` | `oracle.scoring`, docs/tests | `oracle.types` |
| Relative gain / log gain formulas | `rri_metrics.gains` | `oracle.scoring.label_fields`, `rri_metrics.returns`, table adapters | `oracle.rewards`, `rollouts.zarr_store` |
| RRI scalar formula | `rri_metrics.rri` calling `rri_metrics.gains` | scene/target scorers | rollout storage, table helpers |
| Per-candidate `target_rri` label | `oracle.scoring.target_rri` | `rollouts.zarr_store`, app/rerun readers | `rri_metrics.returns`, `rollouts` |
| Per-candidate `target_root_gain` reward label | `oracle.scoring.target_rri`, using `rri_metrics.gains` | `rollouts.zarr_store`, Q_H views, app/rerun readers | `rri_metrics.returns`, `rollouts.zarr_store` |
| Endpoint target gain over selected trajectory | `rri_metrics.returns`, using `rri_metrics.gains` | training/evaluation reports | `oracle`, candidate scorers |
| Discounted selected return | `rri_metrics.returns` | training/evaluation reports, optional store validation | `oracle` |
| Stored replay schema and q_h view | `rollouts.zarr_store` | app, rerun, training loaders | `oracle`, `rri_metrics` |
| Actor-visible target selection | `data_handling.targets.actor_visible` | oracle rollout pipeline, app diagnostics | `oracle`, `rollouts` |
| GT target-task sampling | `data_handling.targets.oracle_tasks` | `oracle.pipelines.rollout_generation` | RRI scorers, rollout storage |
| Target crop policy for RRI labels | `oracle.scoring.target_crop` | `oracle.scoring.target_rri` | `data_handling.targets.geometry` |
| Oracle generation CLIs | `oracle.pipelines.cli` | console scripts | top-level `pipelines`, `rollouts.cli` |

The key correction is that `oracle.rewards` should not exist as a formula owner. `oracle.scoring.label_fields` may own label names, reward modes, and field selection, but all `(before - after) / denom` and log-gain math lives in `rri_metrics.gains`.

## Proposed Module Trees

### `aria_nbv.rri_metrics`

```text
aria_nbv/rri_metrics/
  __init__.py
  AGENTS.md
  point_mesh.py          # DistanceBreakdown, chamfer_point_mesh, chamfer_point_mesh_batched
  gains.py               # differentiable relative/log gain formulas; one source for root + endpoint gain math
  rri.py                 # RriResult plus RRI scalar helpers over point-mesh errors
  returns.py             # discounted returns and endpoint selected-trajectory reducers
  tables.py              # mapping/DataFrame adapters that call gains.py/returns.py; no formulas duplicated
  diagnostics.py         # non-core candidate sanity checks: provenance, invalidity, top-k oracle hit, entropy
  torchmetrics.py        # stateful TorchMetric adapters with typed state attributes and docstrings
  logging.py             # Metric/Loss/LogSpec names, metric_key/loss_key
  plotting.py            # RRI plotting helpers
  objectives/
    __init__.py
    coral.py
    ordinal_binning.py
```

Responsibilities:

- Own metric computation and training/evaluation reductions.
- Make differentiable functions obvious: `gains.py`, `rri.py`, and tensor-facing parts of `returns.py` are differentiable candidates; `tables.py`, `diagnostics.py`, `plotting.py`, and `logging.py` are not.
- Provide TorchMetric adapters over pure functions, not new semantics.

Rules:

- `rri_metrics` must not import `oracle`, `rollouts`, or `data_handling`.
- `tables.py` must not repeat formulas from `gains.py`; scalar wrappers call the same implementation through 0-D tensors or shared scalar helpers in `gains.py`.
- DTOs stay with producers: `DistanceBreakdown` lives in `point_mesh.py`; `RriResult` lives in `rri.py`; return/diagnostic DTOs live beside the return or diagnostic functions that produce them.
- Keep `rri_metrics.__init__` compact. It should not export oracle scorers or pipeline symbols.

### `aria_nbv.oracle`

```text
aria_nbv/oracle/
  __init__.py               # compact scorer/config/label-field API; no pipeline barrel exports
  AGENTS.md
  scoring/
    __init__.py
    label_fields.py         # canonical label names, RriRewardMode, score-field selection; no formulas
    types.py                # OracleCandidateLabels and shared scorer request/evidence DTOs only
    evidence.py             # RootEvalPointCloud, build_root_eval_pointcloud, observed-prefix source semantics
    input_views.py          # render/backproject candidate views into point-cloud evidence
    target_crop.py          # TargetRriInvalidError, OBB point/mesh crop policy
    scene_rri.py            # SceneRriCandidateScorer and config
    target_rri.py           # TargetRriCandidateScorer and config
  pipelines/
    __init__.py             # intentionally empty/minimal; no root re-exports
    scene_labeler.py        # current pipelines/oracle_rri_labeler.py
    rollout_generation.py   # oracle-label rollout dataset generation facade
    rollout_shards.py       # shard planning/status wrappers for oracle-label rollout generation
    cli.py                  # generation command implementation; console names can stay stable
```

Responsibilities:

- `oracle.scoring` owns how oracle-only evidence is assembled and converted into scene/target RRI labels.
- `oracle.scoring` owns target crop policy and expected invalidity for label computation.
- `oracle.pipelines` owns executable composition for oracle-label data generation, not reusable scoring formulas or replay storage.

Rules:

- `oracle.scoring` may import `rri_metrics.point_mesh`, `rri_metrics.rri`, and `rri_metrics.gains`; it must not duplicate point-mesh or gain formulas.
- `oracle.scoring.types` must not contain `RriResult`; that DTO belongs to `rri_metrics.rri`.
- `oracle.scoring.scene_rri` and `oracle.scoring.target_rri` return oracle-owned label DTOs such as `OracleCandidateLabels`. They should not directly own rollout replay DTOs.
- `oracle.pipelines.rollout_generation` may adapt `OracleCandidateLabels` into rollout replay DTOs because the pipeline composes both modules. Keep that adapter private unless at least two callers need it.
- `oracle.scoring` may import `data_handling.targets` for target rows and GT OBB resolution. It must not own target-source selection rules.
- Only `oracle.pipelines` may import `rollouts`; core scorer modules must not.

### `aria_nbv.rollouts`

```text
aria_nbv/rollouts/
  __init__.py
  AGENTS.md
  evaluation.py          # CounterfactualCandidateEvaluation, CounterfactualMetricBundle, evaluator protocol
  trajectory.py          # CounterfactualStepResult, CounterfactualTrajectory, CounterfactualRolloutResult
  selection.py           # CounterfactualSelectionPolicy, selection records and policy helpers
  generator.py           # CounterfactualPoseGenerator and config
  trace.py               # RolloutLineage, RolloutZarrRecord
  zarr_store.py          # schema, writer/reader, validation, q_h derived replay view
  manifest.py            # rollout store manifest
  inspection.py          # read-side tables for app/rerun/CLI
  info_cli.py            # read-only store info/validation CLI
```

Responsibilities:

- Own replay state, selected-action transition records, finite-candidate selection mechanics, lineage, and persistence.
- Derive dense replay/training views from stored fields.
- Provide read-side summaries for Streamlit/Rerun.

Rules:

- `rollouts` must not compute RRI labels or target crops.
- `rollouts.zarr_store` may store, mask, and sum existing label fields, but it must not compute root gain, endpoint gain, or RRI formulas.
- `rollouts.__init__` must not export oracle scorer configs, writer configs, shard build functions, or generation CLIs.
- `info_cli.py` stays because it reads/validates stores. Generation/shard CLIs move to `oracle.pipelines`.
- If `RolloutDatasetWriter` remains temporarily during migration, it should become a private compatibility stepping stone with tests proving no formula ownership. Final ownership for command-facing generation is `oracle.pipelines.rollout_generation`.

### `aria_nbv.data_handling`

```text
aria_nbv/data_handling/
  __init__.py
  efm_dataset.py
  efm_snippet_loader.py
  efm_views.py
  mesh_cache.py
  vin_adapter.py
  vin_oracle_types.py
  _offline_dataset.py
  _offline_store.py
  _offline_format.py
  _offline_writer.py
  targets/
    __init__.py
    types.py             # TargetCandidateRow, OracleTargetTaskRow, result DTOs, invalid reason codes
    actor_visible.py     # ActorVisibleTargetSelector, TargetSelectorConfig
    oracle_tasks.py      # OracleTargetTaskSampler, OracleTargetTaskSamplerConfig
    geometry.py          # target_gt_obb_world, OBB source/world conversion, projection/support helpers
```

Responsibilities:

- Own reading source data and expressing target-source rows.
- Own actor-visible target selection and GT target-task sampling.
- Own target identity and invalidity/audit fields that are properties of source rows, not label computations.

Rules:

- `data_handling.targets` must not render candidate depths, score RRI, compute gains, or write rollout stores.
- `target_gt_obb_world` remains data-handling geometry because it resolves a target row against source GT OBB storage. The actual target RRI crop policy belongs in `oracle.scoring.target_crop`.
- The current `OracleTargetTaskSampler` name is acceptable for a first pass, but the module path should make clear it is a target-task source sampler, not an RRI oracle scorer. A later rename to `GtTargetTaskSampler` would reduce ambiguity.

## Interaction Flow

### One-Step Scene RRI Labeling

```text
data_handling.EfmSnippetView
  -> pose_generation.CandidateViewGenerator
  -> oracle.scoring.input_views.render_backproject_candidates
  -> oracle.scoring.evidence current/root eval points
  -> oracle.scoring.scene_rri.SceneRriCandidateScorer
       uses rri_metrics.point_mesh
       uses rri_metrics.rri / rri_metrics.gains
  -> rri_metrics.rri.RriResult + oracle.scoring.types.OracleCandidateLabels
```

### Target Multi-Step Rollout Generation

```text
data_handling.VinOfflineDataset
  -> data_handling.targets.oracle_tasks or actor_visible target rows
  -> oracle.scoring.target_rri resolves GT label evidence and target crop policy
  -> rollouts.generator creates finite candidate tables
  -> oracle.scoring.target_rri scores candidate labels
       target_rri = state-relative RRI
       target_root_gain = root-normalized reward using rri_metrics.gains
  -> oracle.pipelines.rollout_generation adapts labels to rollout replay DTOs
  -> rollouts.trace / rollouts.zarr_store persists replay and q_h derived view
  -> rollouts.inspection and app/rerun read the store
```

### Training/Evaluation Metric Use

```text
rollouts.zarr_store q_h arrays or candidate tables
  -> rri_metrics.returns discounted_selected_return / endpoint_gain
  -> rri_metrics.diagnostics candidate sanity checks
  -> rri_metrics.torchmetrics stateful Lightning adapters
```

## Endpoint Gain Conflict Resolution

The previous plan was incoherent because it allowed `oracle.rewards`, `rri_metrics.rollout_returns`, `rri_metrics.tables`, and `rollouts.zarr_store` to all compute gain-like values.

Use these exact meanings:

- `target_rri`: per-candidate state-relative RRI label. Produced by `oracle.scoring.target_rri`.
- `target_root_gain`: per-candidate root-normalized target reward. Produced by `oracle.scoring.target_rri` using `rri_metrics.gains.relative_gain(before, after, reference=root_error)`.
- `endpoint_target_gain`: selected-trajectory evaluation metric. Produced by `rri_metrics.returns` using `rri_metrics.gains.relative_gain(initial_error, final_error, reference=initial_error)`.
- `endpoint_log_gain`: selected-trajectory evaluation diagnostic. Produced by `rri_metrics.returns` using `rri_metrics.gains.log_gain`.
- `discounted_selected_return`: selected trajectory return over already-produced rewards. Produced by `rri_metrics.returns`; it does not know how rewards were labeled.
- `td_reward`: stored replay field selected from `target_root_gain`. Owned by `rollouts.zarr_store` as a replay view, not a formula.

Implementation rule:

```text
rri_metrics.gains              owns formulas
oracle.scoring.label_fields    owns label names and reward-mode selection
oracle.scoring.target_rri      owns label production
rollouts.zarr_store            owns storage and q_h projection of labels
rri_metrics.returns            owns training/evaluation reductions over stored labels
```

Any implementation that computes `(before - after) / denom` outside `rri_metrics.gains` should be treated as a refactor violation unless it is a test fixture.

## DTO Placement

Use producer locality first, shared types second:

- `DistanceBreakdown`: `rri_metrics.point_mesh`, because point-mesh functions produce it.
- `RriResult`: `rri_metrics.rri`, because it is the pure RRI metric result and keeps scorer outputs from depending on `oracle.types`.
- `OracleCandidateLabels`: `oracle.scoring.types`, because scene and target scorers and pipelines share it.
- `TargetCandidateRow`, `OracleTargetTaskRow`, target selection/sampling results: `data_handling.targets.types`, because source selectors/samplers produce them and oracle pipelines consume them.
- `CounterfactualCandidateEvaluation`, `CounterfactualMetricBundle`, rollout trajectory DTOs: `rollouts.evaluation` / `rollouts.trajectory`, because replay generation and storage consume them.
- `OracleRriSample`: `oracle.pipelines.scene_labeler`, because the one-step label pipeline produces it and it has no wider consumer yet.
- TorchMetric state DTOs: no separate DTO module. Typed state attributes live on the TorchMetric classes with field docstrings.

Avoid a single package-wide `types.py` unless there are multiple real producers/consumers inside that package and no clearer producer module.

## Redundancies To Collapse

1. Scene and target scorer skeletons duplicate render/backproject/current-eval/score/reward logic.
   - Collapse by introducing `oracle.scoring.input_views`, `oracle.scoring.evidence`, and shared private scorer helpers.

2. Gain formulas are duplicated across rollout scorer helpers and table/tensor reducers.
   - Collapse into `rri_metrics.gains`; make `oracle.scoring.target_rri` and `rri_metrics.returns` call it.

3. Top-level `pipelines` contains Oracle-RRI-specific orchestration.
   - Replace it with `oracle.pipelines`, but keep the subpackage thin and do not export it from `oracle.__init__`.

4. `rollouts.__init__` exports too many public surfaces.
   - Collapse to replay/storage/read-side exports only; generation and scorer exports should fail public-contract tests.

5. `data_handling/_target_selection.py` mixes target DTOs, actor-visible selection, GT target-task sampling, geometry, and scoring-adjacent helpers.
   - Split into `data_handling.targets.*`; keep RRI scoring out.

6. `rri_metrics/metrics/multi_step.py` mixes core differentiable returns and candidate sanity diagnostics.
   - Split into `returns.py` and `diagnostics.py`; label differentiability in module docstrings.

7. `rri_metrics/metrics/multi_step_tables.py` repeats scalar formula logic.
   - Collapse into `tables.py` as adapters over `gains.py` / `returns.py`.

8. `rollouts/inspection.py`, `rollouts/info_cli.py`, and `rollouts/zarr_store.py` duplicate small read helpers.
   - Collapse dictionary/string/fraction helpers into one private read-side helper module only if at least two call sites remain after the larger moves. Do not introduce a public helper surface.

## Implementation Order

1. Add contract tests and stale-path scans for the intended post-refactor roots.
2. Add `rri_metrics.gains`, `rri_metrics.rri`, `rri_metrics.returns`, `rri_metrics.diagnostics`, and `rri_metrics.tables`; move formulas before moving scorers. This removes the largest semantic ambiguity first.
3. Move low-level `OracleRRI`, evidence building, and input preparation into `oracle.scoring`.
4. Move scene/target scorers into `oracle.scoring.scene_rri` and `oracle.scoring.target_rri`, returning oracle-owned label DTOs and metric-owned `RriResult`.
5. Move oracle generation pipelines into `oracle.pipelines`; update console scripts without changing command names; delete top-level `aria_nbv.pipelines` only after imports are green.
6. Narrow `rollouts` exports and split replay DTO/generator modules after scorer/pipeline moves are green.
7. Split `data_handling.targets` after scorer/pipeline moves are stable, unless import cycles force it earlier.
8. Add TorchMetric typed state attributes and docstrings while simplifying `rri_metrics.torchmetrics`.
9. Update docs, AGENTS guidance, generated references, Streamlit imports, and PR validation evidence.

## Review Gate For Execution

A future implementation PR should not be marked ready unless all of these are true:

- Net active LOC across `oracle`, `rri_metrics`, `rollouts`, `pipelines`, and target-selection files decreases.
- No stale active imports remain for `aria_nbv.pipelines`, `aria_nbv.rri_metrics.oracle`, or generation-owned `aria_nbv.rollouts.*`.
- `target_root_gain` is produced in one place and formula-owned by `rri_metrics.gains`.
- `endpoint_target_gain` and `discounted_selected_return` are not produced by `oracle` or `rollouts`.
- `oracle.__init__` does not export pipeline entrypoints.
- A limited rollout dataset can be generated and validated.
- Related Streamlit rollout/RRI pages pass tests or documented smoke checks.
- A GitHub PR exists and required CI is green.

## Independent Review Integration

The independent code-review lane returned `COMMENT`, with no critical or high-severity findings. Its medium findings were integrated by:

- removing `oracle.rewards` as a formula owner;
- keeping `RriResult` out of `oracle.types`;
- adding the explicit supersession/guardrail note for the move from top-level `pipelines` to `oracle.pipelines`;
- documenting that `data_handling.targets` remains source-task ownership, not scoring ownership;
- making root public-contract narrowing part of WP0/WP6.

The independent architecture lane returned `WATCH`, not rejection. Its required changes were integrated by:

- splitting `oracle` into `oracle.scoring` and thin `oracle.pipelines`;
- preserving producer-local DTOs;
- pinning reward/gain semantics by layer;
- preventing core scorer modules from importing `rollouts`.

