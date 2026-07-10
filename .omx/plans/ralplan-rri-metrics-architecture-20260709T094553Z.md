# RALPLAN: `aria_nbv.rri_metrics` Architecture Cleanup

Generated: 2026-07-09T09:45:53Z
Repo: `/home/jd/repos/ARIA-NBV`
Mode: planning only, no package implementation edits

## Decision

Adopt a balanced `rri_metrics` shape with one justified nested module family:
`rollout/`. Collapse shallow one-file folders (`logging/names.py`,
`reporting/plotting.py`) back to top-level modules, remove broad midpoint
re-export surfaces, and split rollout metrics by semantic role:

- differentiable or objective-like tensor returns;
- non-essential rollout/candidate diagnostics;
- dict-row/table presentation adapters;
- stateful TorchMetric adapters.

Do not replace the current shallow folders with a generic `adapters/` package.
That would rename the problem rather than deepening the interface.

## Evidence Base

- `docs/_generated/context/context_snapshot.md:1-29` identifies the
  `make context-heavy` artifact and its source ladder.
- `docs/_generated/context/aria_nbv_tree.md:152-178` shows the current
  `rri_metrics` tree, including one-file `logging/` and `reporting/`
  folders.
- `docs/_generated/context/context_snapshot.md:4986-5228` lists the current
  generated class/module surface for rollout metrics, logging names, oracle
  evidence/scoring, and ordinal objectives.
- `docs/_generated/context/data_contracts.md:1393-1420` exposes only three
  named `rri_metrics` contracts: `LogSpec`, `VinMetricsConfig`, and
  `OracleRRIConfig`.
- `aria_nbv/aria_nbv/rri_metrics/metrics/__init__.py:1-99` re-exports 46
  names. This is the clearest public-surface leak.
- `aria_nbv/aria_nbv/rri_metrics/__init__.py:1-30` is already a compact root
  API and is locked by `aria_nbv/tests/rri_metrics/test_public_api.py`.
- `aria_nbv/aria_nbv/rri_metrics/metrics/multi_step.py:24-136` defines rollout
  DTOs and contains TODOs questioning DTO placement.
- `aria_nbv/aria_nbv/rri_metrics/metrics/multi_step.py:138-263` contains the
  core target-rollout tensors.
- `aria_nbv/aria_nbv/rri_metrics/metrics/multi_step.py:298-804` contains
  candidate and policy diagnostics plus generic candidate reductions.
- `aria_nbv/aria_nbv/rri_metrics/metrics/torchmetrics_multi.py:31-220` shows
  stateful adapters whose `add_state(...)` tensors need typed attributes and
  state docstrings.
- The current thesis state keeps root-normalized target gain as the rollout/Q_H
  return, state-relative RRI as VIN-compatible diagnostic, and log-gain as an
  ablation/diagnostic.

## Architecture Principles

1. A package folder must hide real depth.
   A one-file folder such as `logging/names.py` or `reporting/plotting.py`
   makes imports longer without creating leverage. Use `rri_metrics.logging`
   and `rri_metrics.plotting`.

2. The interface is the test surface.
   Root `rri_metrics.__all__` stays compact. Intermediate modules should not
   re-export large symbol sets unless a public contract test names them.

3. Put DTOs beside the producer when they only describe that producer's return.
   Shared, stable DTOs stay in `types.py`; rollout-only DTOs should live in the
   rollout module that produces them.

4. Separate objective-like tensors from diagnostics.
   `endpoint_target_gain_tensor`, `endpoint_log_gain_tensor`, and
   `discounted_selected_return` are core rollout tensors. Candidate provenance,
   invalid-reason, path-increment, entropy, and top-k oracle-hit helpers are
   diagnostics.

5. Make differentiability explicit.
   Every exported reducer should state one of:
   `differentiable objective candidate`, `differentiable diagnostic`, or
   `non-differentiable diagnostic/report adapter`.

6. TorchMetric state is part of the public contract.
   Every state added with `add_state(...)` gets a class-level typed attribute
   and a concise docstring comment, following the project `python-docstrings`
   guidance and the partial style already present in single-step metrics.

## Proposed Target Tree

```text
aria_nbv/rri_metrics/
  __init__.py                 # compact stable root interface only
  AGENTS.md
  context_pytorch_3d_losses.md

  types.py                    # cross-seam stable RRI result/distance DTOs only
  distance.py                 # point-mesh/chamfer primitives
  logging.py                  # LogSpec, Metric, Loss, metric_key, loss_key
  plotting.py                 # RRI plotting primitives used by app/tests
  single_step.py              # one-step reducers + one-step TorchMetric bundle

  oracle/                     # justified: scoring facade plus evidence builder
    __init__.py               # narrow or empty; no broad re-export bucket
    rri_scorer.py
    evidence_builder.py

  objectives/                 # current objective helpers; keep in first pass
    __init__.py               # narrow stable exports only
    coral.py
    ordinal_binning.py

  rollout/
    __init__.py               # narrow or empty; prefer leaf imports
    returns.py                # core rollout target tensors + TorchRolloutMetrics
    diagnostics.py            # candidate/policy/cost sanity and audit reducers + DTOs
    tables.py                 # dict-row/table adapters for app/CLI summaries
    torchmetrics.py           # stateful multi-step TorchMetrics adapters
```

### Why Only `rollout/` Is Nested

`rollout/` has enough internal structure to deserve a folder: pure tensors,
diagnostic reducers, table adapters, and stateful TorchMetric wrappers. These
are different callers and different test surfaces.

`logging.py` and `plotting.py` do not. They are direct, small public modules.
The current nested forms add path length but no hidden complexity.

`oracle/` and `objectives/` remain nested in the target tree because each has two
real peer modules with related but distinct contracts. Collapsing them to
`oracle.py` or renaming `objectives/` to `ordinal/` is optional later
simplification, not required to fix the current pain.

## Symbol Ownership Map

### `types.py`

Owns only stable cross-seam DTOs:

- `DistanceAggregation`
- `DistanceBreakdown`
- `RriResult`

Do not move rollout DTOs here unless at least two independent seams consume
them as stable contracts. A global types bucket makes producer lookup harder.

### `distance.py`

From current `metrics/point_mesh.py`:

- `chamfer_point_mesh`
- `chamfer_point_mesh_batched`

This module is the actual metric primitive seam for point-mesh computation.
`DistanceBreakdown` stays in `types.py` for the first pass because it is part of
the stable cross-seam RRI result contract. Do not move it during this cleanup
unless a contract test is deliberately updated and all callers are migrated.

### `single_step.py`

From current `metrics/single_step.py` and `metrics/torchmetrics_single.py`:

- `topk_accuracy_from_probs`
- `LabelHistogram`
- `RriErrorStats`
- `VinMetrics`
- `VinMetricsConfig`

Rationale: the one-step reducer surface is small. Splitting stateless and
stateful one-step metrics into different files creates more navigation cost
than benefit.

### `rollout/returns.py`

Core objective-like tensors:

- `TorchRolloutMetrics`
- `discounted_selected_return`
- `endpoint_target_gain_tensor`
- `endpoint_log_gain_tensor`
- `summarize_selected_rollout_tensors`

Differentiability labels:

- `discounted_selected_return`: differentiable objective candidate when inputs
  are model-produced rewards/returns and masks are fixed.
- `endpoint_target_gain_tensor`: differentiable objective candidate for
  endpoint target gain if endpoint errors come from a differentiable path.
  In current oracle/replay usage it is a supervised target/evaluation metric.
- `endpoint_log_gain_tensor`: differentiable diagnostic/ablation, not the
  primary thesis return.
- `summarize_selected_rollout_tensors`: mixed reducer; each field inherits the
  status of the underlying tensor.

### `rollout/diagnostics.py`

Non-core rollout/candidate sanity checks:

- `CandidateOrderConsistency`
- `SelectedActionOracleComparison`
- `CandidatePathIncrementStats`
- `CandidatePrimaryInvalidReasonStats`
- `candidate_order_consistency`
- `candidate_policy_entropy`
- `candidate_topk_oracle_hit`
- `selected_action_oracle_comparison`
- `candidate_provenance_share`
- `candidate_path_increment_stats`
- `candidate_primary_invalid_reason_share`
- `candidate_masked_mean`
- `candidate_best_value`
- `selected_path_length_tensor`

Differentiability labels:

- `candidate_policy_entropy`, `candidate_masked_mean`, and
  `candidate_best_value` are differentiable diagnostics under fixed masks,
  except at max/tie points for `candidate_best_value`.
- `selected_path_length_tensor` is a differentiable acquisition-cost diagnostic
  with respect to camera-center tensors under fixed masks, not a primary RRI
  objective.
- `candidate_topk_oracle_hit`, `candidate_order_consistency`,
  `selected_action_oracle_comparison`, provenance shares, path-increment
  summaries, and invalid-reason summaries are non-differentiable diagnostics or
  reporting reducers.

Private helper placement:

- Tiny helper functions from current `multi_step.py` should stay private in the
  leaf that uses them.
- It is acceptable to duplicate a two-line private shape/mask helper once if it
  avoids a new shared bucket.
- Do not add `rollout/utils.py` unless a real import cycle or repeated helper
  body appears during implementation.

### `rollout/tables.py`

From current `metrics/multi_step_tables.py`:

- `TargetRolloutMetricSummary`
- `selected_target_reward`
- `selected_target_rri`
- `finite_horizon_target_return`
- `endpoint_target_gain`
- `endpoint_log_gain`
- `target_point_mesh_error_before`
- `target_point_mesh_error_after`
- `summarize_target_rollout_metrics`

This is a report adapter over stored rollout row dictionaries. It is not a
training objective module and should not be imported by differentiable training
code.

### `rollout/torchmetrics.py`

From current `metrics/torchmetrics_multi.py`:

- `FiniteMeanMetric`
- `SelectedRolloutMetrics`
- `CandidateTableMetrics`
- `CandidatePathIncrementMetric`
- `CandidatePrimaryInvalidReasonMetric`
- `SelectedPathCostMetrics`
- `CandidateOrderConsistencyMetric`
- `CandidatePolicyEntropyMetric`
- `CandidateTopKOracleHitMetric`
- `CandidateProvenanceShareMetric`
- `SelectedActionOracleComparisonMetric`

Every class must declare state attributes above `__init__`, for example:

```python
class FiniteMeanMetric(MetricBase):
    """Accumulate a finite mean for scalar rollout/table values."""

    full_state_update = False

    total: Tensor
    """Finite value sum accumulated across updates."""

    count: Tensor
    """Number of finite values included in `total`."""
```

### `logging.py`

From current `logging/names.py`:

- `LogSpec`
- `Logable`
- `Metric`
- `Loss`
- `metric_key`
- `loss_key`

This is a small naming-policy module. It should not live under a one-file
folder. `LogSpec` is a named contract and should keep field docstrings.

### `plotting.py`

From current `reporting/plotting.py`:

- `rri_color_map`
- `plot_rri_scores`
- `plot_pm_distances`
- `plot_pm_accuracy`
- `plot_pm_completeness`
- `plot_rri_scene`

Remove `_histogram_overlay` and `_plot_hist_counts_mpl` from this module's
`__all__`; import those helpers from their real owner if tests/app panels need
them.

## Public Import Policy

Allowed root exports:

- `OracleRRI`, `OracleRRIConfig`
- `RriResult`, `DistanceAggregation`, `DistanceBreakdown`
- point-mesh primitives if already locked by public tests
- `RriOrdinalBinner`, `ordinal_labels_to_levels`
- CORAL helpers already treated as stable public VIN training helpers

Disallowed midpoint bucket:

- `aria_nbv.rri_metrics.metrics.__all__` with dozens of names.

Preferred import style after the cleanup:

```python
from aria_nbv.rri_metrics.rollout.returns import endpoint_target_gain_tensor
from aria_nbv.rri_metrics.rollout.diagnostics import candidate_topk_oracle_hit
from aria_nbv.rri_metrics.rollout.torchmetrics import SelectedRolloutMetrics
from aria_nbv.rri_metrics.logging import Metric, metric_key
from aria_nbv.rri_metrics.plotting import plot_rri_scores
```

## DTO Policy

Use this rule set:

1. Cross-seam DTOs live in `types.py`.
   Example: `RriResult` is produced by `OracleRRI` and consumed by plotting,
   app panels, tests, and serialization. It deserves a stable shared type.

2. Return-shape DTOs live beside their producer.
   Example: `TorchRolloutMetrics` is returned only by
   `summarize_selected_rollout_tensors`, so it belongs in `rollout/returns.py`.

3. Diagnostic DTOs live beside diagnostic producers.
   Example: `CandidatePathIncrementStats` belongs in
   `rollout/diagnostics.py`.

4. Config/factory DTOs live beside the constructed class.
   Example: `VinMetricsConfig` belongs in `single_step.py`; `OracleRRIConfig`
   belongs in `oracle/scorer.py`.

5. Do not create `types/rollout.py` unless a real import cycle appears or the
   DTOs become stable contracts across more than one seam.

## Work Packages

### WP0: Lock Public Intent

Goal: prevent another broad accidental interface.

Edits:

- Strengthen `aria_nbv/tests/rri_metrics/test_public_api.py` so it asserts that
  root `__all__` stays compact and no midpoint `metrics.__all__` exposes the
  whole package.
- Add expected-import tests for the new intended leaves before or during moves.

Stop condition:

- Tests fail on the current broad `metrics/__init__.py` surface or encode the
  target import shape before the move is completed.

### WP1: Collapse Shallow Folders

Goal: remove unjustified nesting.

Edits:

- Move `logging/names.py` to `logging.py`.
- Move `reporting/plotting.py` to `plotting.py`.
- Remove `logging/__init__.py` and `reporting/__init__.py`.
- Update app, Lightning, tests, generated API refs, and docs by mechanical
  import retargeting only.
- Remove private plotting helpers from `rri_metrics.plotting.__all__`.

Stop condition:

- No stale imports matching
  `rri_metrics\.(logging\.names|reporting\.plotting)`.

### WP2: Split Rollout Metrics By Semantic Role

Goal: make core rollout returns and diagnostics obvious.

Edits:

- Create `rollout/returns.py` from the core top block of `metrics/multi_step.py`.
- Create `rollout/diagnostics.py` from candidate/policy diagnostics.
- Create `rollout/tables.py` from `metrics/multi_step_tables.py`.
- Create `rollout/torchmetrics.py` from `metrics/torchmetrics_multi.py`.
- Move rollout DTOs next to their producer modules.
- Update tests and callers to import from the new leaf modules; do not change
  app, Lightning, VIN, rollout, or data behavior.
- Add module docstrings that state differentiability and objective/diagnostic
  status.
- Keep private helpers local to the leaf that uses them; do not introduce a
  generic helper module unless a real cycle appears.

Stop condition:

- Core functions listed in the user prompt only live in `rollout/returns.py`.
- Candidate sanity helpers only live in `rollout/diagnostics.py`.

### WP3: Type And Document TorchMetric States

Goal: make stateful adapters inspectable and safe to extend.

Edits:

- In `rollout/torchmetrics.py`, add typed state attributes and state docstrings
  for every `add_state(...)` tensor.
- Apply the same standard to remaining stateful one-step classes in
  `single_step.py` if any state is still undocumented.
- Add a focused contract test, for example
  `tests/rri_metrics/test_torchmetric_state_contracts.py`, that parses the
  TorchMetric modules and checks every `add_state("name", ...)` has a
  class-level `name: Tensor` annotation and adjacent string-literal field
  docstring.
- Keep comments concise and contract-focused; no tutorial prose.

Stop condition:

- `uv run pytest tests/rri_metrics/test_torchmetric_state_contracts.py` passes
  and would fail for an undocumented new TorchMetric state.

### WP4: Collapse The Old `metrics/` Package

Goal: remove the broad midpoint namespace.

Edits:

- Move `metrics/point_mesh.py` to `distance.py`.
- Merge `metrics/single_step.py` and `metrics/torchmetrics_single.py` into
  `single_step.py`.
- Delete `metrics/__init__.py` once imports are updated.
- Prefer no `metrics/` folder. If compatibility tests force a temporary
  compatibility path, document it as deprecated and keep it out of root docs.

Stop condition:

- No active production/test imports use
  `rri_metrics.metrics.(multi_step|torchmetrics_multi|torchmetrics_single|point_mesh|single_step|multi_step_tables)`.

### WP5: Keep Or Narrow `oracle/` And `objectives/`

Goal: avoid scope creep while addressing obvious pain.

Default:

- Keep `oracle/` and `objectives/` as real subpackages because they each have two
  peer modules and non-trivial contracts.
- Do not rename `objectives/` to `ordinal/` in the first implementation pass.
  `objectives/` is not as shallow as logging/reporting, and current app,
  Lightning, and test imports already use it.

Optional later simplification:

- Collapse to `oracle.py`, or rename `objectives/` to `ordinal/`, only if
  import fan-out remains low and public docs become clearer. This is not
  required for the first cleanup PR.

## Validation Plan

Run from repo root unless noted:

```bash
cd aria_nbv
uv run ruff format --check aria_nbv/rri_metrics tests/rri_metrics
uv run ruff check aria_nbv/rri_metrics tests/rri_metrics
uv run pytest tests/rri_metrics
uv run pytest tests/rri_metrics/test_torchmetric_state_contracts.py
uv run pytest tests/vin/test_rri_binning.py tests/vin/test_coral.py
uv run pytest tests/lightning/test_vin_batch_collate.py
uv run pytest tests/rollouts/test_counterfactuals.py
uv run pytest tests/data_handling/test_vin_offline_store.py
```

Static import checks:

```bash
rg -n "rri_metrics\.(logging\.names|reporting\.plotting)" aria_nbv docs
rg -n "rri_metrics\.metrics\.(multi_step|multi_step_tables|point_mesh|single_step|torchmetrics_multi|torchmetrics_single)" aria_nbv docs
rg -n "from aria_nbv\.rri_metrics\.metrics import|import aria_nbv\.rri_metrics\.metrics" aria_nbv docs
```

Docs and context:

```bash
./scripts/quarto_generate_api_docs.sh
make context-heavy
```

Only run `graphify update .` after implementation edits, not for this planning
artifact alone.

## Acceptance Criteria

- `rri_metrics/logging.py` and `rri_metrics/plotting.py` exist; the old
  one-file folders are gone.
- `rri_metrics/metrics/__init__.py` is gone or no longer a broad public bucket.
- Core rollout return tensors are discoverable under
  `rri_metrics.rollout.returns`.
- Diagnostic candidate helpers are discoverable under
  `rri_metrics.rollout.diagnostics`.
- Every exported reducer docstring says whether it is objective-like,
  differentiable, or diagnostic/report-only.
- Every TorchMetric state has a typed class attribute and state docstring.
- A TorchMetric state-contract test enforces the typed state/docstring pattern.
- Root `rri_metrics.__all__` is compact and stable.
- Cross-surface changes outside `rri_metrics` are mechanical import retargeting
  only.
- No claim is made that Q_H, target descriptors, target-conditioned scoring, or
  new metric semantics were implemented.

## RALPLAN Decision Record

### Option A: Minimal Collapse Only

Collapse `logging/` and `reporting/`, leave `metrics/` as is.

Pros:

- Lowest churn.
- Solves the user's most obvious nesting complaint.

Cons:

- Leaves the 891 LOC `multi_step.py` semantic mix.
- Leaves the 46-name `metrics/__all__` leak.
- Does not make differentiability or core-vs-diagnostic status clear.

Verdict: insufficient.

### Option B: One Deep `rollout/` Family Plus Shallow Collapse

Adopt the target tree above.

Pros:

- Fixes the actual navigation problem without broad restructuring.
- Uses one justified nested folder where there is real internal depth.
- Keeps DTOs close to producer functions.
- Gives tests clear seams.

Cons:

- Moderate import churn.
- Requires careful generated docs update.

Verdict: recommended.

### Option C: Full Top-Level Flattening

Move everything to top-level files: `oracle.py`, `ordinal.py`, `distance.py`,
`logging.py`, `plotting.py`, `single_step.py`, `rollout_*.py`.

Pros:

- Very shallow and easy to grep.

Cons:

- Reintroduces a flat package once rollout grows.
- Makes rollout metric roles less visually grouped.
- Risks another broad module list as the package grows.

Verdict: too flat for the rollout path.

### Option D: Generic `adapters/` Package

Move logging, plotting, and TorchMetrics wrappers under `adapters/`.

Pros:

- Names stateful/non-core wrappers explicitly.

Cons:

- Another broad taxonomy bucket.
- Logging names are not adapters over metric computation; they are log-key
  contracts.
- Plotting is not structurally related to TorchMetrics.

Verdict: reject for this cleanup.

## Execution Staffing

Direct solo execution is viable. If using OMX/Codex subagents:

- `executor`: WP1-WP2 import moves and file splits.
- `test-engineer`: public API tests, stale import checks, TorchMetric state
  audit script/check.
- `writer`: generated API docs and `rri_metrics/AGENTS.md`.
- `critic` or `code-reviewer`: post-diff review for public-surface creep and
  accidental semantic changes.

Avoid a large team unless WP0-WP4 are deliberately split into separate workers
with disjoint write sets.

## Non-Goals

- No Q_H implementation.
- No new target descriptors.
- No target-conditioned scoring changes.
- No scene-memory package.
- No broad VIN or Lightning rewrite.
- No broad `data_handling` or app-panel cleanup.

## Artifacts

- Context handoff:
  `.omx/context/rri-metrics-architecture-20260709T094553Z.md`
- Visual architecture review:
  `.omx/specs/rri-metrics-architecture-review-20260709T094553Z.html`
