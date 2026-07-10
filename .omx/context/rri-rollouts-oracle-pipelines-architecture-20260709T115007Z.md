# RRI, Rollout, Oracle, and Pipeline Architecture Context

Created: 2026-07-09T11:50:07Z

## Task

Revise the earlier `rri_metrics`-only architecture handoff so it also covers
responsibility leakage between `aria_nbv.rri_metrics`, `aria_nbv.rollouts`, and
`aria_nbv.pipelines`.

The desired outcome is a simpler module hierarchy with clearer seams:

- metric computation is separate from oracle label generation;
- oracle RRI supports scene-level single-step labels and target-conditioned
  multi-step rollout labels;
- rollout replay/storage stays in `rollouts`;
- top-level data-generation orchestration lives in `pipelines`;
- redundant scorer/evidence/reward logic is concentrated behind fewer
  interfaces.

This is a planning-only pass. Package implementation code is not edited.

## Active Constraints

- Do not implement `Q_H`.
- Do not implement target descriptors.
- Do not change scoring semantics or reward definitions.
- Do not broaden VIN, Lightning, or `data_handling` refactors.
- Do not leave long-term compatibility facades unless public contract tests
  prove an external import is still active.
- Preserve command names such as `nbv-build-rollouts`,
  `nbv-plan-rollout-shards`, and `nbv-status-rollout-shards` even if the owning
  modules move.

## Prior Handoff Being Superseded

`.omx/plans/ralplan-rri-metrics-architecture-handoff-20260709T094553Z.json`
planned only the `aria_nbv.rri_metrics` tree. It explicitly treated rollout
changes as out-of-scope beyond mechanical imports. The new request changes that
scope: rollout scorer and data-generation ownership must be included.

## Current Trees

```text
aria_nbv/aria_nbv/rri_metrics
├── logging/names.py
├── metrics/{multi_step.py,multi_step_tables.py,point_mesh.py,single_step.py,torchmetrics_multi.py,torchmetrics_single.py}
├── objectives/{coral.py,ordinal_binning.py}
├── oracle/{evidence.py,scorer.py}
├── reporting/plotting.py
└── types.py

aria_nbv/aria_nbv/rollouts
├── cli.py
├── counterfactuals.py
├── dataset_writer.py
├── info_cli.py
├── inspection.py
├── manifest.py
├── shard_manifest.py
├── shards.py
├── target_counterfactuals.py
├── trace.py
└── zarr_store.py

aria_nbv/aria_nbv/pipelines
└── oracle_rri_labeler.py
```

Approximate current size for the involved packages is 14k LOC. The largest
files are `rollouts/zarr_store.py` (3056), `rollouts/counterfactuals.py`
(1542), `rollouts/inspection.py` (1410), `rollouts/dataset_writer.py` (966),
`rri_metrics/metrics/multi_step.py` (891), and
`rri_metrics/metrics/torchmetrics_multi.py` (692).

## Evidence

### Graphify

`graphify query "ARIA-NBV rri_metrics rollouts pipelines oracle RRI counterfactual target rollout architecture redundancies"`
returned the central cluster around:

- `rollouts/zarr_store.py`
- `rollouts/counterfactuals.py`
- `rollouts/target_counterfactuals.py`
- `rollouts/dataset_writer.py`
- `rollouts/shards.py`
- `pipelines/oracle_rri_labeler.py`
- `rri_metrics/metrics/__init__.py`
- app and Rerun rollout readers

This confirms `rollouts` is currently central for storage, replay DTOs, target
scoring, generation orchestration, and read-side summaries.

### Package Guidance Conflict

`aria_nbv/aria_nbv/rollouts/AGENTS.md` currently says `rollouts` owns:

- target-cropped oracle rollout scoring;
- VIN-source rollout generation;
- rollout-generation recipes;
- the `nbv-build-rollouts` CLI.

That conflicts with the new direction and prior memory: synthetic Oracle-RRI
counterfactual rollout generation should live in `aria_nbv.pipelines`, while
`rollouts` should become replay/storage/inspection.

### Oracle Label Semantics Already Live Partly in `rri_metrics`

`rri_metrics/oracle/scorer.py` owns the base `OracleRRI` point-mesh facade and
says target-specific callers pass target-cropped points and meshes; invalid
crops must not fall back to scene-level labels.

`rri_metrics/oracle/evidence.py` owns root/current evaluation point-cloud
construction and the source distinction between ASE GT depth, legacy semidense
points, and reserved rendered logged depth.

### Oracle Label Semantics Still Leak Into `rollouts`

`rollouts/target_counterfactuals.py` implements:

- target crop policy constants;
- `TargetRriInvalidError`;
- `CounterfactualTargetOracleRriScorerConfig`;
- `CounterfactualTargetOracleRriScorer`;
- target OBB mesh crop helpers;
- target point crop helpers;
- root/current eval-point caching;
- reward mode conversion to `target_root_gain` vs `target_rri`;
- optional scene RRI diagnostics.

`rollouts/counterfactuals.py` implements:

- `CounterfactualOracleRriScorerConfig`;
- `CounterfactualOracleRriScorer`;
- root-normalized gain and log-gain helpers;
- `_eval_depth_far_m`;
- root/current eval-point caching for scene RRI.

These are oracle label and reward semantics, not replay/storage semantics.

### Generation Orchestration Currently Lives in `rollouts`

`rollouts/dataset_writer.py` says it reads `VinOfflineDataset`, selects targets,
generates candidate tables, scores with the target-cropped oracle, and writes a
standalone `rollouts.zarr` store.

`rollouts/cli.py` implements `nbv-build-rollouts`,
`nbv-plan-rollout-shards`, and `nbv-status-rollout-shards`.

`rollouts/shards.py` opens source datasets, plans source-row shard manifests,
runs strict temp-to-final shard builds, and summarizes rollout shard campaigns.

These are pipeline orchestration modules.

### Metric Reducers Mix Core Returns and Diagnostics

`rri_metrics/metrics/multi_step.py` contains core differentiable rollout
reducers:

- `discounted_selected_return`;
- `endpoint_target_gain_tensor`;
- `endpoint_log_gain_tensor`;
- `summarize_selected_rollout_tensors`.

It also contains non-core diagnostics:

- `candidate_order_consistency`;
- `candidate_policy_entropy`;
- `candidate_topk_oracle_hit`;
- `selected_action_oracle_comparison`;
- `candidate_provenance_share`;
- `candidate_path_increment_stats`;
- `candidate_primary_invalid_reason_share`.

Those functions are useful, but the current module gives them the same status
as training-return primitives.

## Relevant Generated Context

Generated context currently records:

- `counterfactual-transition`: selected candidate depth/render update and
  deterministic replay state transition;
- `relative-reconstruction-improvement`: mesh-supervised RRI via point-mesh
  error and `rri_metrics.oracle.scorer`;
- `target-conditioned-nbv-mdp`: the contract connecting target-conditioned
  rollout generation, reward computation, validity masks, and finite-horizon
  value learning.

The thesis text in
`docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ`
distinguishes all-candidate labels for scorer training from selected-transition
rollouts for `Q_H`, and treats target RRI reward as the primary rollout reward.

## Open Design Questions

1. Should there be a top-level `aria_nbv.oracle` package?
2. Which `rollouts` contents belong in `rri_metrics`?
3. Which `rollouts` contents belong in `pipelines`?
4. How should rollout result DTOs relate to oracle scorer result DTOs?
5. How much compatibility should be kept during the move?

## Working Answers

1. Do not create top-level `aria_nbv.oracle` yet. There is one real oracle
   family in scope: RRI labels. A top-level package would be a shallow taxonomy
   until a second oracle family exists.
2. Move oracle label semantics into `rri_metrics.oracle`: scene rollout scorer,
   target rollout scorer, target crop policies, target invalidity, root/current
   eval assembly, reward conversion helpers.
3. Move data-generation orchestration into `pipelines.rollout_generation`:
   writer, recipes, selected-depth retention, shard planning/execution, shard
   campaign status, and CLI implementation.
4. In the first implementation pass, avoid a broad DTO migration. Keep rollout
   replay DTOs in `rollouts`, and introduce an oracle-owned score result only if
   it breaks an import cycle or reduces duplication. Do not let `rri_metrics`
   become a storage package.
5. Prefer clean moves. Temporary facades are allowed only for public root
   imports or entrypoint compatibility, and they should be deprecation shims with
   tests and a removal target.

