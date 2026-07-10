# ARIA-NBV Oracle Module Refactor Plan

Created: 2026-07-09T12:32:31Z  
Status: superseded-by-corrected-autoresearch-artifact  
Supersedes: `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-handoff-20260709T115007Z.json`

> Corrected on 2026-07-09 by
> `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md`.
> The high-level decision to create `aria_nbv.oracle` still stands. The
> module tree below is not executable as written where it assigns
> root-normalized gain or log-gain formulas to `oracle/rewards.py`. Formula
> ownership belongs to metrics, specifically a `gains`/`returns` seam.
> `oracle` may own label-field names and reward-mode selection only.

## Requirements Summary

Refactor the current RRI, rollout, and pipeline ownership into a deeper module centered on a new `aria_nbv.oracle` package. The requested architecture change is deliberate: scene and target RRI scorers, oracle evidence/input preparation, and data-generation pipelines move under `aria_nbv.oracle` instead of maintaining the current `aria_nbv.pipelines` package.

The refactor must improve locality and reduce degrees of freedom. `rri_metrics` should become the metric-computation module only; `rollouts` should own replay/storage/inspection only; `oracle` should own label semantics and generation pipelines; `app` should remain a UI adapter. The resulting diff must reduce net package LOC, not just reshuffle files.

## Current Evidence

Graphify query used:

```bash
graphify query "ARIA-NBV current rri_metrics rollouts pipelines Oracle RRI target counterfactual scorer redundant implementations where should aria_nbv.oracle own scene target evidence input preparation pipelines"
```

Graphify surfaced the dense cluster around `rollouts/zarr_store.py`, `rollouts/counterfactuals.py`, `rollouts/target_counterfactuals.py`, `rollouts/dataset_writer.py`, `rollouts/shards.py`, `pipelines/oracle_rri_labeler.py`, `rri_metrics/oracle/*`, and rollout Streamlit pages.

Concrete current-state findings:

- `rollouts/counterfactuals.py` mixes replay DTOs, rollout pose generation, reward helpers, and scene Oracle-RRI scorer logic. Reward/eval helpers live at lines 120-159, replay-facing DTOs at 288-380, and `CounterfactualOracleRriScorer` at 702-850.
- `rollouts/target_counterfactuals.py` owns target Oracle-RRI label semantics, including target crop policy, invalidity, scorer config, root eval cache, OBB crop helpers, and scene-diagnostic scoring. See lines 1-19, 62-153, 188-240, and 396-470.
- `rri_metrics/oracle/evidence.py` already owns root evaluation point-cloud construction and source semantics. See `RriEvaluationPointCloudSource`, `RriRewardMode`, `RootEvalPointCloud`, and `build_root_eval_pointcloud` at lines 24-129.
- `rri_metrics/oracle/scorer.py` owns the base `OracleRRI` point-mesh scorer, but it is currently buried under a metrics package despite being an oracle label module. See lines 40-81 and 154-263.
- `pipelines/oracle_rri_labeler.py` is already an oracle pipeline, not a general pipeline. It generates candidates, renders depth, backprojects point clouds, and calls `OracleRRI.score` at lines 33-39 and 80-157.
- `rollouts/dataset_writer.py`, `rollouts/shards.py`, `rollouts/shard_manifest.py`, and `rollouts/cli.py` implement data-generation orchestration. Writer config and rollout target/scorer composition are at `dataset_writer.py` lines 268-326; the writer run loop is at 464-560; CLI entrypoints are at `cli.py` lines 46-64 and 67-260.
- Console scripts still point to `aria_nbv.rollouts.cli` in `aria_nbv/pyproject.toml` lines 91-93.
- `rollouts/__init__.py` is too broad: it re-exports scorer, writer, shard, CLI-adjacent, inspection, trace, and Zarr symbols at lines 10-168.
- `rri_metrics/metrics/multi_step.py` mixes differentiable/core rollout returns with non-essential sanity diagnostics. Core return functions are at lines 138-240; ranking/provenance/path/invalidity diagnostics are at lines 299-760.
- `rri_metrics/metrics/multi_step.py` still contains TODOs saying DTO placement is unsettled at lines 24, 68, 93, and 117.
- `rri_metrics/metrics/torchmetrics_multi.py` state is created via `add_state` without typed attribute declarations or field docstrings. See repeated `add_state` calls at lines 42-45, 85-93, 172-180, 233-242, 304-312, 514-515, 569-570, and 616-623.
- Redundant helper implementations exist across rollout readers/inspectors: `_read_string_array` is duplicated in `rollouts/zarr_store.py` at lines 2782 and 3038, and similar `_safe_fraction` / `_component_names` helpers exist in `rollouts/info_cli.py` and `rollouts/inspection.py`.

## Design Principles

1. **Deep module over package shuffle.** `aria_nbv.oracle` must hide render/backproject/evidence/crop/scoring/pipeline details behind small scorer and pipeline interfaces.
2. **One adapter equals a hypothetical seam.** Do not introduce a new adapter layer unless there are at least two real callers or it deletes duplicated orchestration.
3. **Producer-owned DTOs by default.** Keep DTOs with the function/class that produces them unless a DTO is genuinely shared across packages.
4. **Metric semantics stay explicit.** Differentiable/core training objectives must be visibly separated from diagnostic sanity checks.
5. **Reduced LOC is an acceptance criterion.** Compatibility facades, duplicate helper modules, and empty one-file directories are not allowed unless contract tests prove they are needed.

## Decision Drivers

- Label semantics currently require bouncing between `rollouts`, `rri_metrics.oracle`, and `pipelines`; this hurts locality.
- The final thesis/data pipeline treats scene RRI and target RRI as oracle-label generation, not ordinary metrics.
- The app pages and rollout store readers must continue to function after the refactor, so the plan must preserve CLI names, store schema, and Streamlit entry behavior while moving module ownership.

## Viable Options

### Option A: Keep Oracle Under `rri_metrics.oracle`

Move only target/scene scorers from `rollouts` to `rri_metrics.oracle`, and move generation orchestration under `rri_metrics.oracle.pipelines`.

Pros: small conceptual delta from current code; fewer package roots.  
Cons: keeps oracle label generation under a package named `metrics`, which conflicts with the user's requested architecture and continues to blur metric computation vs oracle supervision.

Decision: rejected.

### Option B: Dedicated `aria_nbv.oracle` Package

Create `aria_nbv.oracle` as the deep module for scene/target RRI scorers, evidence/input preparation, and oracle-label pipelines. Move metric-only reducers out of the oracle path.

Pros: best locality; matches requested seam; clarifies that target-RRI rollout labels are oracle supervision; allows deletion of `aria_nbv.pipelines`.  
Cons: larger import migration; requires careful public contract tests and docs updates.

Decision: chosen.

### Option C: Keep Pipelines Top-Level, Move Only Scorers

Create `aria_nbv.oracle` for scorers/evidence but keep `aria_nbv.pipelines` for all data generation.

Pros: less CLI/doc churn.  
Cons: contradicts the user constraint that pipelines must live with oracle, and preserves a shallow package whose only active file is already Oracle-RRI-specific.

Decision: rejected.

## ADR

Decision: introduce `aria_nbv.oracle` and delete the active `aria_nbv.pipelines` package after moving its content under `aria_nbv.oracle.pipelines`.

Drivers: reduce cross-package bouncing for label semantics, make oracle supervision a first-class module, keep `rri_metrics` metric-only, and reduce public surfaces.

Alternatives considered: keep oracle under `rri_metrics.oracle`; keep top-level `pipelines`; move everything into `rollouts`.

Why chosen: `oracle` is the only seam that can own both scene and target RRI label semantics plus the generation pipelines without overloading either `rri_metrics` or `rollouts`.

Consequences: import paths and docs move; CLI command names stay stable; public contract tests must be updated; guidance files must be changed so future work does not reintroduce pipeline/scorer ownership into `rollouts`.

Follow-ups: after this refactor, `zarr_store.py` schema simplification and app read-model unification should be separate PRs unless needed to keep LOC negative.

## Target Module Tree

```text
aria_nbv/
  oracle/
    AGENTS.md
    __init__.py                  # compact stable oracle interface
    evidence.py                  # RootEvalPointCloud, source modes, root/current eval assembly
    inputs.py                    # render/backproject input preparation shared by scene and target pipelines
    label_fields.py              # RriRewardMode and emitted label-field selection; no gain formulas
    scoring.py                   # OracleRRI, OracleRRIConfig, scene scorer config/scorer
    target.py                    # target crop policy, invalidity, target scorer config/scorer
    types.py                     # only cross-oracle DTOs, e.g. RriResult if not co-located in scoring.py
    pipelines/
      __init__.py
      scene_labels.py            # current pipelines/oracle_rri_labeler.py
      rollout_dataset.py         # writer, recipe config, selected-depth retention
      rollout_shards.py          # shard manifest + shard execution/status
      rollout_cli.py             # nbv-build-rollouts, nbv-plan-rollout-shards, nbv-status-rollout-shards impl

  rri_metrics/
    AGENTS.md
    __init__.py                  # compact metric/objective root only
    point_mesh.py                # Chamfer / point-mesh primitives and DistanceBreakdown
    gains.py                     # root-normalized gain, log gain, endpoint gain formulas
    single_step.py               # one-step pure reducers
    rollout_returns.py           # differentiable/core multi-step returns
    rollout_diagnostics.py       # non-core rollout sanity diagnostics
    torchmetrics.py              # stateful metric adapters with typed states/docstrings
    logging.py                   # metric/loss names; no logging/names.py directory
    plotting.py                  # plotting helpers; no reporting/plotting.py directory
    objectives/
      coral.py
      ordinal_binning.py

  rollouts/
    AGENTS.md
    __init__.py                  # replay/storage/inspection exports only
    counterfactuals.py           # transition replay, selection policies, generator, replay DTOs
    trace.py
    zarr_store.py
    manifest.py
    inspection.py
    info_cli.py
```

Deleted or emptied active packages after import updates:

```text
aria_nbv/pipelines/
aria_nbv/rri_metrics/oracle/
aria_nbv/rri_metrics/logging/
aria_nbv/rri_metrics/reporting/
aria_nbv/rri_metrics/metrics/
aria_nbv/rollouts/target_counterfactuals.py
aria_nbv/rollouts/dataset_writer.py
aria_nbv/rollouts/cli.py
aria_nbv/rollouts/shards.py
aria_nbv/rollouts/shard_manifest.py
```

If public contract tests show one of these paths is externally stable, add a narrow deprecation wrapper only for that specific path and record its removal issue. Otherwise, do not add compatibility facades.

## DTO Placement Rule

Use this rule during implementation:

- DTOs produced by exactly one module and consumed only by that module's callers stay beside the producer. Example: `OracleRriSample` moves with `oracle/pipelines/scene_labels.py`.
- DTOs shared by multiple oracle scorers or pipelines move to `oracle/types.py`. Example candidates: `RootEvalPointCloud` only if both evidence and target/scene scorer modules need to type it publicly; otherwise it stays in `oracle/evidence.py`.
- Metric result DTOs stay with metric primitives when the function is the true producer. Example: `DistanceBreakdown` should move beside `point_mesh.py` if it is only the point-mesh return type.
- Rollout replay DTOs stay in `rollouts.counterfactuals` or `rollouts.trace`. Example: `CounterfactualCandidateEvaluation` and `CounterfactualMetricBundle` remain replay adapter DTOs unless moving them to `oracle.types` demonstrably deletes import cycles and duplicate conversion code.

## Workpackages

### WP0 - Baseline, Guardrails, and LOC Gate

Goal: prove the refactor is behavior-preserving and net-smaller before edits start.

Steps:

1. Capture baseline LOC for `aria_nbv/aria_nbv/oracle` if present, `rri_metrics`, `rollouts`, and `pipelines` using `wc -l`.
2. Add or update public contract tests that pin the intended stable roots after the move:
   - `aria_nbv.oracle`
   - `aria_nbv.oracle.pipelines`
   - `aria_nbv.rri_metrics`
   - `aria_nbv.rollouts`
3. Add stale-path scans to the final verification script for old `rri_metrics.oracle`, `aria_nbv.pipelines`, and generation-owned `aria_nbv.rollouts.*` imports.
4. Define success as net-negative LOC across `aria_nbv/aria_nbv/{oracle,rri_metrics,rollouts,pipelines}` plus tests/docs excluding generated reference files.

Acceptance:

- Baseline LOC artifact exists in `.omx/context/` or PR description.
- Tests fail for stale public roots before the move or are updated in the same commit as the move.
- No implementation semantics are changed in WP0.

### WP1 - Create `aria_nbv.oracle` and Move Oracle Semantics

Goal: make oracle label semantics local.

Moves:

- `rri_metrics/oracle/evidence.py` -> `oracle/evidence.py`.
- `rri_metrics/oracle/scorer.py` -> `oracle/scoring.py`.
- `rollouts/target_counterfactuals.py` -> `oracle/target.py`.
- scene scorer section of `rollouts/counterfactuals.py` lines 702-850 -> `oracle/scoring.py`.
- reward-mode / emitted-label selection from `rollouts/counterfactuals.py` lines 120-159 -> `oracle/label_fields.py`.
- root-normalized gain and log-gain formulas from `rollouts/counterfactuals.py` lines 120-159 -> `rri_metrics/gains.py`.
- render/backproject candidate input preparation shared by `pipelines/oracle_rri_labeler.py` and rollout scorers -> `oracle/inputs.py`.

Collapse targets:

- Replace duplicated scene/target scorer skeletons with a shared internal score path for: render candidate depths, backproject, build current eval points, call `OracleRRI.score`, convert distances to reward.
- Keep target OBB crop functions local to `oracle/target.py` unless a second non-target caller appears.
- Remove `OracleRRI.score_batch` if stale-import scans and tests show no live caller.

Acceptance:

- Scene and target scorer public imports come from `aria_nbv.oracle`.
- `rri_metrics` no longer imports or exports `OracleRRI`, `OracleRRIConfig`, `RootEvalPointCloud`, or target invalidity types except through a deliberate root compatibility test if required.
- `rollouts.counterfactuals` can call an oracle evaluator via `CounterfactualEvaluatorFn` without owning label semantics.

### WP2 - Move Oracle Pipelines Under `aria_nbv.oracle.pipelines`

Goal: delete top-level `aria_nbv.pipelines` as an active package.

Moves:

- `pipelines/oracle_rri_labeler.py` -> `oracle/pipelines/scene_labels.py`.
- `rollouts/dataset_writer.py` -> `oracle/pipelines/rollout_dataset.py`.
- `rollouts/shard_manifest.py` and `rollouts/shards.py` -> `oracle/pipelines/rollout_shards.py`, unless combining them makes the file too large to navigate.
- `rollouts/cli.py` -> `oracle/pipelines/rollout_cli.py`.
- Update `aria_nbv/pyproject.toml` console scripts at lines 91-93 to point to `aria_nbv.oracle.pipelines.rollout_cli`.

Collapse targets:

- Remove duplicate selected-depth and writer helper shims that only existed because writer lived in `rollouts`.
- Keep user-facing command names unchanged: `nbv-build-rollouts`, `nbv-plan-rollout-shards`, `nbv-status-rollout-shards`.
- Remove `aria_nbv/pipelines/__init__.py` and the top-level package unless public contract tests prove it must remain as a temporary deprecation facade.

Acceptance:

- `uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml --dry-run` uses `aria_nbv.oracle.pipelines.rollout_cli`.
- Docs/reference no longer list `reference/pipelines*.qmd` except as archived migration notes.
- Rollout generation imports no longer originate from `aria_nbv.rollouts`.

### WP3 - Narrow `rollouts` to Replay, Storage, and Inspection

Goal: make `rollouts` a deep replay/storage module instead of a mixed generation/scoring namespace.

Steps:

- Update `rollouts/__init__.py` to export replay DTOs, selection policy, generator, trace, manifest, Zarr reader/writer, and inspection helpers only.
- Remove scorer, writer, shard, and CLI exports from `rollouts/__init__.py`.
- Update `rollouts/AGENTS.md`: rollouts owns replay records, counterfactual transitions, trace, Zarr stores, manifests, inspection, and info CLI only.
- Keep `rollouts/info_cli.py` because it reads stores; move shard campaign status CLI to `oracle.pipelines`.

Collapse targets:

- Deduplicate `_safe_fraction`, `_component_names`, and dictionary/string-array helpers between `inspection.py`, `info_cli.py`, and `zarr_store.py`.
- Do not start the full `zarr_store.py` schema refactor in this PR unless it is needed to keep LOC negative and tests are already green.

Acceptance:

- `tests/rollouts/test_public_api.py` asserts no scorer/writer/pipeline exports from `aria_nbv.rollouts`.
- `tests/rollouts` still passes.
- Streamlit rollout pages still import reader/inspection helpers from `rollouts`, not generation/scoring code.

### WP4 - Simplify `rri_metrics` Around Metric Computation

Goal: make `rri_metrics` navigable and metric-only.

Moves:

- `metrics/point_mesh.py` -> `point_mesh.py`.
- `metrics/single_step.py` -> `single_step.py`.
- Split `metrics/multi_step.py` into:
  - `rollout_returns.py`: `discounted_selected_return`, `endpoint_target_gain_tensor`, `endpoint_log_gain_tensor`, `summarize_selected_rollout_tensors`, candidate `masked_mean` / `best_value` if used as objective support.
  - `rollout_diagnostics.py`: `candidate_topk_oracle_hit`, `candidate_provenance_share`, `candidate_path_increment_stats`, `candidate_primary_invalid_reason_share`, order consistency, policy entropy, selected-action oracle comparison.
- Merge `metrics/torchmetrics_single.py` and `metrics/torchmetrics_multi.py` into `torchmetrics.py` only if the result remains readable; otherwise keep `torchmetrics_single.py` / `torchmetrics_rollout.py` at top level.
- `logging/names.py` -> `logging.py`.
- `reporting/plotting.py` -> `plotting.py`.

DTO rule:

- Move `TorchRolloutMetrics` beside `summarize_selected_rollout_tensors` in `rollout_returns.py`.
- Move diagnostic DTOs beside their producers in `rollout_diagnostics.py`.
- Remove `types.py` if all DTOs have clear producers; otherwise keep it only for truly shared cross-module DTOs.

TorchMetric state rule:

- Add explicit typed state attributes and attribute docstrings to every TorchMetric class before or immediately after `add_state`.
- Keep state names identical unless tests and checkpoint compatibility prove they can change.

Acceptance:

- `rri_metrics` root exports are compact and objective/metric-only.
- Core differentiable returns are not co-located with non-essential sanity diagnostics.
- All TorchMetric classes have typed state attributes and docstrings per `python-docstrings`.

### WP5 - App, Docs, and Reference Alignment

Goal: keep UI and public docs aligned with the new seam.

Steps:

- Update app imports in rollout, RRI, and VIN diagnostics panels.
- Update `docs/reference/_api_index.md`, `docs/reference/_sidebar.yml`, and the Quarto generation script so `oracle` replaces `pipelines` and old nested metrics paths.
- Update `docs/typst/seminar_paper/sections/05-oracle-rri.typ`, setup docs, and any diagrams that name `pipelines/oracle_rri_labeler.py`.
- Update `.configs/*.toml` type strings only where they are active config targets.
- Add `aria_nbv/aria_nbv/oracle/AGENTS.md` and update `rri_metrics/AGENTS.md` and `rollouts/AGENTS.md`.

Acceptance:

- No stale docs/import hits for old active paths:
  - `aria_nbv.pipelines`
  - `aria_nbv.rri_metrics.oracle`
  - `aria_nbv.rollouts.target_counterfactuals`
  - `aria_nbv.rollouts.dataset_writer`
  - `aria_nbv.rollouts.cli`
  - `aria_nbv.rollouts.shards`
  - `aria_nbv.rri_metrics.logging.names`
  - `aria_nbv.rri_metrics.reporting.plotting`

### WP6 - End-to-End Rollout Dataset and Streamlit Validation

Goal: prove the new architecture still supports the product-facing workflows.

Steps:

1. Generate a new limited rollout dataset with a smoke config or a new deliberately small config derived from `.configs/build_rollouts_v1_smoke.toml`.
2. Validate the generated store with `validate_rollout_zarr_store` and `nbv-rollouts-info`/equivalent reader checks.
3. Run Streamlit panel tests for offline dataset, RRI, stored rollouts, counterfactual rollouts, and VIN diagnostics pages.
4. If feasible in CI, add a headless app import/smoke test that imports all page modules and constructs their reader dependencies without launching a browser.

Acceptance:

- A new limited rollout dataset is generated during local validation and referenced in the PR evidence.
- Store validation passes.
- Related Streamlit app page tests pass.
- No page imports `oracle` pipeline code unless it is explicitly running a generation workflow.

### WP7 - Branch, PR, and CI Gate

Goal: do not call the refactor complete until GitHub CI proves it.

Steps:

1. Create a dedicated branch from current main.
2. Commit only request-traceable source, docs, tests, and guidance changes.
3. Push and open a PR with:
   - module tree before/after
   - LOC baseline vs final
   - stale-path scan output
   - generated limited rollout dataset command and validation output
   - local test matrix
4. Monitor CI and fix failures until all required checks pass.

Acceptance:

- PR exists.
- Required GitHub CI checks are green.
- Net LOC across touched active package files is reduced.
- Any remaining compatibility wrappers have dated removal follow-ups.

## Verification Plan

Run locally before PR:

```bash
cd aria_nbv
uv run ruff format --check aria_nbv/oracle aria_nbv/rri_metrics aria_nbv/rollouts tests/rri_metrics tests/rollouts tests/app
uv run ruff check aria_nbv/oracle aria_nbv/rri_metrics aria_nbv/rollouts tests/rri_metrics tests/rollouts tests/app
uv run pytest tests/rri_metrics
uv run pytest tests/rollouts
uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py
uv run pytest tests/app/panels/test_stored_rollouts_panel.py
uv run pytest tests/data_handling/test_vin_offline_store.py
uv run pytest tests/lightning/test_vin_batch_collate.py
uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml --dry-run
```

Generate and validate a limited rollout dataset:

```bash
cd aria_nbv
uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_smoke.toml
uv run nbv-rollouts-info <generated-store-path> --validate --stats
```

Run stale-path scans:

```bash
rg -n "aria_nbv\\.pipelines|from aria_nbv import pipelines|rri_metrics\\.oracle|rollouts\\.(target_counterfactuals|dataset_writer|cli|shards|shard_manifest)|rri_metrics\\.logging\\.names|rri_metrics\\.reporting\\.plotting" aria_nbv docs .configs
```

Docs and context:

```bash
./scripts/quarto_generate_api_docs.sh
make context-heavy
make check-agent-memory
```

PR/CI:

```bash
gh pr create --draft --fill
gh pr checks --watch
```

## Risks and Mitigations

- Risk: moving config target classes breaks TOML deserialization. Mitigation: update config strings and run config field constraint tests plus dry-run CLI before generation.
- Risk: import migration adds compatibility wrappers and increases LOC. Mitigation: public contract tests decide wrappers; otherwise old modules are deleted.
- Risk: `oracle` grows too broad. Mitigation: only oracle label semantics and oracle data-generation pipelines live there; rollout store reading remains in `rollouts`, metric math remains in `rri_metrics`.
- Risk: Streamlit pages depend on old broad roots. Mitigation: app tests and import smoke tests are required before PR completion.
- Risk: generated rollout dataset requires unavailable local data. Mitigation: plan execution must either use the existing smoke config on available local data or add a tiny test fixture path; PR cannot be marked complete without a successful limited dataset generation command or an explicit CI artifact replacement.

## Non-Goals

- Do not implement `Q_H`.
- Do not implement new target descriptors or target-conditioned VIN scoring.
- Do not reinterpret RRI, target invalidity, or q-train masks.
- Do not broadly refactor `data_handling`, VIN, or Lightning.
- Do not perform the full `zarr_store.py` schema-engine rewrite unless the scoped refactor cannot meet the LOC gate without a small local deduplication.

## Execution Handoff

Recommended workflow: `$ultragoal` as the durable leader, with `$team` for parallel execution lanes once WP0/WP1 interfaces are pinned.

Suggested lanes:

- `executor`: WP1/WP2 import moves and package creation.
- `test-engineer`: public contract tests, stale-path scans, Streamlit tests, limited rollout dataset generation.
- `writer`: docs/reference/guidance updates.
- `verifier`: LOC gate, CI evidence, PR checks.
- `critic`: final review for package-shuffle without depth, unintended compatibility wrappers, and LOC inflation.

Stop condition: merged or merge-ready PR with green CI, generated limited rollout dataset validation, functional related Streamlit pages, stale-path scans clean, and net active LOC reduction documented in the PR.
