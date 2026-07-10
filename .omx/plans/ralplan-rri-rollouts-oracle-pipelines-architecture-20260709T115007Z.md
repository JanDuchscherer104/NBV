# Revised RALPLAN: RRI, Oracle, Rollout, and Pipeline Module Architecture

Created: 2026-07-09T11:50:07Z

Status: superseded

> Superseded on 2026-07-09 by
> `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md`.
> Do not execute this plan as written. Its chosen option keeps oracle label
> semantics under `rri_metrics.oracle` and generation under top-level
> `pipelines`; the current execution direction is a dedicated
> `aria_nbv.oracle` package whose pipelines live under `oracle.pipelines`.
> Metric formulas remain in metrics, not in oracle.

Supersedes:
`.omx/plans/ralplan-rri-metrics-architecture-handoff-20260709T094553Z.json`

## Outcome

Simplify the RRI/rollout/data-generation architecture by making each module
deeper:

- `rri_metrics` owns metric meaning and oracle label semantics.
- `rri_metrics.oracle` owns both single-step scene RRI and target-conditioned
  rollout RRI scorers plus the evidence builders they need.
- `rollouts` owns replay state, transition expansion, Zarr storage, manifests,
  and read-side inspection.
- `pipelines` owns top-level data-generation orchestration, including rollout
  writer, shard execution, and CLI implementation.

No scoring semantics, target descriptors, `Q_H`, VIN models, Lightning logic, or
large `data_handling` split is part of this plan.

## RALPLAN-DR Summary

### Principles

1. One scientific meaning has one owning module.
2. Data-generation orchestration is not replay storage.
3. Oracle-only evidence must not leak into actor-visible rollout state.
4. A nested module earns its place only when it gives locality and leverage.
5. Public root interfaces stay compact; specialized imports come from leaves.

### Decision Drivers

1. Target-conditioned rollout labels are thesis-core and must be easier to
   audit than the current scattered scorer path.
2. `rollouts` is overloaded with scoring, generation, storage, and inspection.
3. The previous rri-only plan would improve navigation inside `rri_metrics` but
   leave the largest responsibility leak untouched.

### Viable Options

#### Option A: Deepen `rri_metrics.oracle`, move generation to `pipelines`

Keep RRI oracle label semantics under `rri_metrics.oracle`, keep replay/storage
under `rollouts`, and move writer/shard/CLI orchestration under
`pipelines.rollout_generation`.

Pros:

- Best locality for RRI label semantics.
- Avoids a shallow top-level `oracle` package.
- Matches existing `pipelines/oracle_rri_labeler.py` precedent.
- Keeps `rollouts` focused on replay and storage.

Cons:

- Requires careful import-cycle handling between oracle scorer adapters and
  rollout replay DTOs.
- Requires docs/reference path churn.

Verdict: chosen.

#### Option B: Create top-level `aria_nbv.oracle`

Move all oracle label code out of `rri_metrics` into `aria_nbv.oracle`.

Pros:

- Makes oracle importance highly visible.
- Could host future non-RRI oracle families.

Cons:

- Today there is only one real oracle family, so the seam is hypothetical.
- `rri_metrics` would still own the base metric and reward names, increasing
  cross-module knowledge.
- More public churn without immediate leverage.

Verdict: reject for now; reopen only when there are at least two non-RRI oracle
families or an import cycle makes `rri_metrics.oracle` unworkable.

#### Option C: Keep scorers in `rollouts`, only move writer/CLI to `pipelines`

Treat target scorers as rollout adapters and move only data-generation
orchestration.

Pros:

- Smaller first diff.
- Fewer immediate imports changed.

Cons:

- Leaves target crop policy, invalidity, root evidence, and reward conversion
  outside the oracle module.
- Does not solve the duplication between scene and target scorer skeletons.
- Keeps the most important label semantics in a replay/storage package.

Verdict: reject; it fails the stated goal.

## ADR

### Decision

Adopt Option A. Do not create top-level `aria_nbv.oracle` in this refactor.
Deepen the existing `rri_metrics.oracle` module and move rollout
data-generation orchestration to `pipelines.rollout_generation`.

### Drivers

- Target RRI and scene RRI are variants of the same point-mesh oracle label
  family.
- Rollout replay/storage has a different interface from oracle label scoring.
- Pipeline orchestration already exists in `pipelines/oracle_rri_labeler.py` and
  should be the home for dataset-writing jobs and CLIs.
- Top-level `oracle` would be shallow until a second oracle family exists.

### Alternatives Considered

- Top-level `aria_nbv.oracle`: rejected as premature.
- Keep scorers in `rollouts`: rejected because it preserves the current leak.
- Keep the previous rri-only plan: rejected because it ignores the largest
  cross-package redundancy.

### Consequences

- `rollouts/AGENTS.md` must be updated because it currently encodes stale
  ownership.
- Docs/reference entries and generated context paths must be regenerated.
- Imports in tests, app panels, Rerun inspector, and CLI tests must be updated
  carefully.
- Existing command names remain stable even if implementation modules move.

## Explicit Adapter Seam

The scorer move must not blur oracle scoring and replay storage. Use this seam:

- `rri_metrics.oracle` owns oracle-label computation: evidence construction,
  target crop policy, invalidity, point-mesh scoring, root/log gain conversion,
  and candidate score selection.
- `rollouts` owns replay-facing adapters:
  `CounterfactualCandidateEvaluation` and `CounterfactualMetricBundle` remain
  in `rollouts` for the first implementation pass because the rollout
  generator, RL env, and UI adapters already consume that shape.
- `rri_metrics.oracle.rollout_scorers` may import the replay adapter DTOs as an
  adapter target, but it must not own Zarr fields, rollout persistence, branch
  schedules, or selected-action replay state.
- If an import cycle appears, introduce a small oracle-owned DTO named for the
  scorer result, for example `OracleCandidateScores`, and convert it to
  `CounterfactualCandidateEvaluation` inside `rollouts` or
  `pipelines.rollout_generation`. Do not move storage fields into the oracle
  DTO.

This pins the interface: oracle modules produce label semantics; rollout
modules adapt those semantics into replay records.

## Pipelines Package Interface

`aria_nbv.pipelines` should expose executable data-generation pipelines, not
metric primitives or replay storage:

- `pipelines.oracle_rri_labeler` remains the single-step scene RRI/VIN label
  pipeline.
- `pipelines.rollout_generation` becomes the public module for target-RRI
  rollout build/plan/status orchestration.
- Public imports for rollout generation should move to:
  - `aria_nbv.pipelines.rollout_generation.writer`
  - `aria_nbv.pipelines.rollout_generation.shards`
  - `aria_nbv.pipelines.rollout_generation.shard_manifest`
  - `aria_nbv.pipelines.rollout_generation.cli`
- User-facing command names stay unchanged:
  `nbv-build-rollouts`, `nbv-plan-rollout-shards`, and
  `nbv-status-rollout-shards`.

## Target Tree

```text
aria_nbv/rri_metrics/
  __init__.py                 # compact stable interface only
  AGENTS.md
  types.py                    # cross-seam RRI distance/result DTOs only
  distance.py                 # point-mesh metric primitive, current metrics/point_mesh.py
  logging.py                  # current logging/names.py, no subfolder
  plotting.py                 # current reporting/plotting.py, no subfolder
  single_step.py              # one-step reducers and one-step TorchMetrics

  rollout/
    __init__.py               # empty or narrow
    returns.py                # differentiable/core target-rollout return tensors
    diagnostics.py            # non-core candidate/path/provenance sanity checks
    tables.py                 # current mapping/table summary reducers
    torchmetrics.py           # stateful adapters over returns + diagnostics

  oracle/
    __init__.py               # narrow exports: OracleRRI and scorer configs
    scorer.py                 # OracleRRI point-mesh facade only
    evidence.py               # root/current eval point-cloud builders
    rewards.py                # root gain, log gain, reward-mode conversion helpers
    target_crop.py            # target OBB crop policy and invalidity
    rollout_scorers.py        # scene + target rollout scorer adapters

  objectives/
    __init__.py
    coral.py
    ordinal_binning.py

aria_nbv/rollouts/
  __init__.py                 # replay/storage/inspection surface only
  counterfactuals.py          # pose-tree expansion, selection policy, replay DTOs
  trace.py
  zarr_store.py
  manifest.py
  inspection.py
  info_cli.py

aria_nbv/pipelines/
  __init__.py
  oracle_rri_labeler.py       # existing single-step label pipeline
  rollout_generation/
    __init__.py
    writer.py                 # current rollouts/dataset_writer.py
    recipes.py                # rollout recipe/target-source configs if split pays
    selected_depth.py         # selected-depth retention config if split pays
    shards.py                 # current rollouts/shards.py
    shard_manifest.py         # generation campaign manifest
    cli.py                    # command implementation, entrypoint names unchanged
```

## Symbol Ownership Map

### Move from `rollouts` to `rri_metrics.oracle`

- `CounterfactualOracleRriScorer`
- `CounterfactualOracleRriScorerConfig`
- `CounterfactualTargetOracleRriScorer`
- `CounterfactualTargetOracleRriScorerConfig`
- `TargetRriInvalidError`
- `TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1`
- `SCENE_CROP_POLICY_SNIPPET_EXTENT_V1`
- target OBB point/mesh crop helpers
- root/current eval point assembly shared by scene and target rollout scorers
- root-normalized gain/log-error gain/reward-mode selection helpers
- `_eval_depth_far_m` or its public equivalent

### Keep in `rollouts`

- `CounterfactualPoseGenerator`
- `CounterfactualPoseGeneratorConfig`
- `CounterfactualSelectionPolicy`
- `CounterfactualSelectionRecord`
- `CounterfactualTrajectory`
- `CounterfactualStepResult`
- `CounterfactualRolloutResult`
- `CounterfactualCandidateEvaluation`
- `CounterfactualMetricBundle`
- `RolloutLineage`
- `RolloutZarrRecord`
- `RolloutZarrStoreReader`
- `write_rollout_zarr_store`
- `validate_rollout_zarr_store`
- read-side inspection helpers
- `info_cli.py` for inspecting existing rollout stores

### Move from `rollouts` to `pipelines.rollout_generation`

- `RolloutDatasetWriter`
- `RolloutDatasetWriterConfig`
- `RolloutDatasetWriterStats`
- `RolloutRecipeConfig`
- `SelectedDepthRetentionConfig`
- `RolloutTargetSource`
- `_RolloutSourceLineageBuilder`
- shard planning and strict shard execution functions/classes
- `RolloutShardEntry` and `RolloutShardRow` if treated as generation campaign
  manifests; keep in `rollouts` only if they become persisted store schema
  records rather than campaign inputs
- build/plan/status CLI implementation

### Keep in `rri_metrics.rollout.returns`

These are core and potentially differentiable training/evaluation quantities:

- `discounted_selected_return`
- `endpoint_target_gain_tensor`
- `endpoint_log_gain_tensor`
- `summarize_selected_rollout_tensors`
- `TorchRolloutMetrics`

### Keep in `rri_metrics.rollout.diagnostics`

These are useful but non-core sanity checks:

- `selected_path_length_tensor`
- `candidate_order_consistency`
- `candidate_policy_entropy`
- `candidate_topk_oracle_hit`
- `selected_action_oracle_comparison`
- `candidate_provenance_share`
- `candidate_path_increment_stats`
- `candidate_primary_invalid_reason_share`
- their diagnostic DTOs

## DTO Policy

Use a producer-local DTO policy:

- Cross-seam, stable scientific DTOs stay in `rri_metrics/types.py`.
- Result DTOs returned by core return reducers live beside the reducer module.
- Diagnostic DTOs live beside diagnostic producers.
- Config/factory DTOs live beside the class they construct.
- Replay/storage DTOs stay in `rollouts`.
- Generation campaign DTOs live in `pipelines.rollout_generation`.
- Mixed scorer/replay adapter DTOs stay in `rollouts` unless a concrete import
  cycle forces a narrow oracle-owned scorer result DTO. If that happens, the
  oracle DTO must contain label semantics only, and conversion to replay DTOs
  must happen outside `rri_metrics.oracle`.
- Do not create a broad `types/` package unless a concrete import cycle or
  stable cross-seam contract appears.

This makes a symbol's source file more apparent: core return DTOs are in
`rollout/returns.py`; diagnostic DTOs are in `rollout/diagnostics.py`; oracle
scorer configs are in `oracle/rollout_scorers.py`; rollout replay DTOs are in
`rollouts/counterfactuals.py` or `rollouts/trace.py`.

## Public Import Policy

- Keep `aria_nbv.rri_metrics.__init__` compact:
  `OracleRRI`, `OracleRRIConfig`, `RriResult`, distance DTOs, CORAL helpers,
  `RriOrdinalBinner`, and the primary rollout return helpers only if public
  tests require root imports.
- Keep `aria_nbv.rollouts.__init__` focused on replay/storage/inspection.
- Add or update public contract tests before deleting current root exports.
- Prefer leaf imports for specialized surfaces:
  - `aria_nbv.rri_metrics.oracle.rollout_scorers`
  - `aria_nbv.rri_metrics.rollout.returns`
  - `aria_nbv.rri_metrics.rollout.diagnostics`
  - `aria_nbv.pipelines.rollout_generation.writer`
- Avoid midpoint barrels that recreate the old flat interface.

## Workpackages

### WP0: Lock Current Public Intent

Goal: prevent accidental behavior or public-interface drift before moving code.

Actions:

- Add or tighten public contract tests for root exports in
  `aria_nbv.rri_metrics`, `aria_nbv.rollouts`, and `aria_nbv.pipelines`.
- Record expected command entrypoints for rollout build/plan/status.
- Record that invalid targets/crops are hard invalidity, not low RRI.
- Add stale-import scan commands to the test plan.

Acceptance:

- The tests make it obvious which imports are intentionally stable and which
  module paths are allowed to move.

### WP1: Move Oracle Rollout Scorers into `rri_metrics.oracle`

Goal: concentrate oracle label semantics in one module.

Actions:

- Obsolete action: do not create `rri_metrics/oracle/rewards.py` as a formula
  owner. The corrected plan in
  `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md` assigns
  root/log/endpoint gain formulas to metrics and leaves only label-field or
  reward-mode selection with oracle.
- Create `rri_metrics/oracle/target_crop.py` for target crop constants,
  `TargetRriInvalidError`, OBB point/mesh crop helpers, and target crop extent.
- Create `rri_metrics/oracle/rollout_scorers.py` for scene and target rollout
  scorer configs/classes.
- Deduplicate scene and target scorer skeletons around a small internal scoring
  context: render candidate depth, build candidate point clouds, build current
  eval points, score via `OracleRRI`, then emit score/result payload.
- Keep `OracleRRI` in `oracle/scorer.py`; do not make it know about rollout
  trajectories.
- Keep target invalidity semantics unchanged.

Acceptance:

- `rollouts/counterfactuals.py` no longer imports `OracleRRIConfig`,
  `build_root_eval_pointcloud`, or `canonical_fuse_points` for scorer logic.
- `rollouts/target_counterfactuals.py` is deleted or reduced to a temporary
  tested deprecation shim only if a public import contract requires it.
- `CounterfactualCandidateEvaluation` and `CounterfactualMetricBundle` remain
  the rollout replay adapter shape, or a narrow `OracleCandidateScores`-style
  DTO is introduced only to break a proven cycle.
- `tests/rollouts/test_counterfactuals.py` and `tests/rri_metrics` still cover
  scene and target scoring behavior.

### WP2: Move Rollout Generation Orchestration into `pipelines`

Goal: make top-level data generation a pipeline concern.

Actions:

- Create `pipelines/rollout_generation/`.
- Move `rollouts/dataset_writer.py` to
  `pipelines/rollout_generation/writer.py`.
- Move `rollouts/shards.py` to `pipelines/rollout_generation/shards.py`.
- Move `rollouts/shard_manifest.py` to
  `pipelines/rollout_generation/shard_manifest.py` unless implementation
  proves it is persisted replay-store schema.
- Move `rollouts/cli.py` to `pipelines/rollout_generation/cli.py`.
- Keep package entrypoint command names unchanged.
- Update tests from `tests/rollouts/test_dataset_writer.py` and
  `tests/rollouts/test_cli_typer.py` to a pipeline-oriented test location or
  import path while preserving behavior.

Acceptance:

- `rollouts` no longer imports VIN offline datasets or target selectors for
  writer orchestration.
- `pipelines.rollout_generation` imports `rollouts` for replay/store and
  imports `rri_metrics.oracle` for scoring.
- Existing rollout build/plan/status commands still work.

### WP3: Narrow `rollouts` to Replay, Storage, and Inspection

Goal: make `rollouts` a deep replay/storage module rather than a catch-all.

Actions:

- Update `rollouts/__init__.py` to export replay DTOs, generator policies,
  store read/write, manifest, and inspection surfaces only.
- Keep `CounterfactualPoseGenerator` and trajectory/step DTOs in
  `rollouts/counterfactuals.py`, or split to `rollouts/generation.py` only if
  it reduces interface size without creating another shallow module.
- Keep `info_cli.py` because it inspects existing rollout stores.
- Remove writer/scorer/shard exports from the rollout root unless public tests
  require temporary deprecation shims.
- Update `rollouts/AGENTS.md` to match the new owner surface.

Acceptance:

- `rollouts/AGENTS.md` no longer says rollouts owns target-aware oracle
  scorers, dataset writer, shard generation, or build CLI implementation.
- App/Rerun read-side code imports only replay/storage/read-side symbols from
  `rollouts`.

### WP4: Finish the `rri_metrics` Navigation Cleanup

Goal: make core metric computation and diagnostics visibly different.

Actions:

- Collapse unjustified shallow folders:
  - `logging/names.py` -> `logging.py`
  - `reporting/plotting.py` -> `plotting.py`
- Move `metrics/point_mesh.py` -> `distance.py`.
- Move one-step reducers/TorchMetrics to `single_step.py` if this does not
  make the file too broad; otherwise use `single_step_metrics.py` and
  `single_step_torchmetrics.py`.
- Create `rollout/returns.py`, `rollout/diagnostics.py`, `rollout/tables.py`,
  and `rollout/torchmetrics.py`.
- Type every TorchMetric `add_state` field as a class attribute and document
  state fields per the `python-docstrings` skill.
- Delete or narrow `rri_metrics/metrics/__init__.py`.

Acceptance:

- Core differentiable return helpers are not mixed with provenance/invalidity
  sanity checks.
- Public root and midpoint export tests prevent the old broad surface from
  returning.

### WP5: Align Docs, Generated API, and Guidance

Goal: keep humans and agents from following stale paths.

Actions:

- Update `aria_nbv/AGENTS.md`,
  `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`, and
  `aria_nbv/aria_nbv/rollouts/AGENTS.md`.
- Add a `pipelines/AGENTS.md` if pipeline ownership now has enough rules to
  justify a local guide.
- Update Quarto reference navigation and generated API docs.
- Update thesis references that name `rollouts.target_counterfactuals` as the
  owner of target RRI scoring.
- Run `make context-heavy` after the code move so generated context no longer
  points to stale owner modules.

Acceptance:

- `rg` scans for old owner paths return only deliberate deprecation shims or
  historical notes.

## Workpackage Order

1. WP0: lock public intent.
2. WP1: move oracle rollout scorers.
3. WP2: move data-generation orchestration.
4. WP3: narrow rollout exports and guidance.
5. WP4: finish metric navigation cleanup.
6. WP5: regenerate docs/context and update guides.

This order moves scientific label semantics before pipeline orchestration, then
narrowly cleans the original `rri_metrics` hierarchy once the cross-package
seams are correct.

## Test Plan

Run targeted checks after each implementation slice, then the combined suite.

```bash
cd aria_nbv
uv run ruff format --check aria_nbv/rri_metrics aria_nbv/rollouts aria_nbv/pipelines tests/rri_metrics tests/rollouts
uv run ruff check aria_nbv/rri_metrics aria_nbv/rollouts aria_nbv/pipelines tests/rri_metrics tests/rollouts
uv run pytest tests/rri_metrics
uv run pytest tests/rollouts/test_counterfactuals.py
uv run pytest tests/rollouts/test_dataset_writer.py tests/rollouts/test_cli_typer.py
uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py
uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py
uv run pytest tests/rerun_inspector/test_rollout_zarr_logger.py
uv run pytest tests/data_handling/test_vin_offline_store.py
uv run pytest tests/lightning/test_vin_batch_collate.py
uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml --dry-run
```

Stale import/reference scans:

```bash
rg -n "aria_nbv\\.rollouts\\.(target_counterfactuals|dataset_writer|cli|shards|shard_manifest)" aria_nbv docs
rg -n "rollouts\\.(target_counterfactuals|dataset_writer|cli|shards|shard_manifest)" aria_nbv docs
rg -n "rri_metrics\\.(logging\\.names|reporting\\.plotting|metrics\\.(multi_step|multi_step_tables|point_mesh|torchmetrics_multi|torchmetrics_single))" aria_nbv docs
```

Docs/context:

```bash
./scripts/quarto_generate_api_docs.sh
make context-heavy
make check-agent-memory
```

## Available Agent Types and Follow-up Staffing

- `executor`: implement one workpackage at a time.
- `test-engineer`: add public contract tests and stale-import scans before
  moves.
- `explore`: map import fanout before each move.
- `writer`: update AGENTS and docs/reference notes after code settles.
- `critic`: review for shallow replacement modules and stale compatibility
  surfaces before merging.

Recommended follow-up:

- Use `$ultragoal` as the durable sequential leader for WP0-WP5.
- Use `$team` inside WP1/WP2 if parallel lanes are needed:
  - lane A: oracle scorer move;
  - lane B: import/test map;
  - lane C: pipeline writer/CLI move after scorer move lands;
  - lane D: docs/guidance update after imports are stable.
- Use `$ralph` only as an explicit fallback for a single-owner persistence loop
  if team coordination becomes noisy.

## Risks and Mitigations

- Risk: `rri_metrics.oracle` imports rollout DTOs and creates a cycle.
  Mitigation: keep replay DTOs in `rollouts` for the first pass; introduce a
  small oracle-owned score result only if the cycle appears.
- Risk: generated docs and public root imports hide stale paths.
  Mitigation: add public import tests and stale `rg` scans before deleting old
  modules.
- Risk: moving writer/shards changes CLI behavior.
  Mitigation: keep entrypoint names unchanged and run CLI dry-run tests.
- Risk: metric cleanup becomes a second broad refactor.
  Mitigation: defer WP4 until scorer and pipeline ownership are correct.
- Risk: top-level `oracle` remains tempting.
  Mitigation: record the ADR that one adapter means a hypothetical seam; reopen
  only when a second oracle family exists.

## Stop Condition

The plan is ready for execution when Architect and Critic both approve the
handoff and the durable JSON record marks the consensus gate complete. No
package code should be modified by this planning session.
