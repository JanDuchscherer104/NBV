# Target Selection Rework Autoresearch

Status: complete for the current iteration.

## Executive Synthesis

The current V1 target-selection implementation is mostly aligned with the
important source-boundary contract: actor-visible observed or predicted targets
are selected first, and GT objects are used afterward for labels, matching, and
evaluation. I did not find evidence that the normal V1 selector uses GT OBBs as
actor-visible target input.

The main mismatch is now methodological, not a simple leakage bug. The current
implementation still chooses targets through a scalar interest score plus
`greedy_top_k` or `temperature_softmax_top_k`. The newer requirement from the
`019ed4da-5d8f-7740-a68e-e2ee800d7bee` discussion is different: build an
actor-visible pool of labelable targets, then sample relatively uniformly or
stratified across useful bins. The selector should expose target diversity and
hard-turn coverage, not silently collapse to the single most convenient or most
undersupported object.

The next implementation should therefore add a stratified-uniform target-pool
policy while preserving the existing OBS-SEL / PRED-Q / GT-EVAL split. GT
matching should remain deterministic and geometry-first after actor-visible
eligibility unless a concrete validation failure justifies adding more matching
terms.

## Source Map

High-trust current implementation and tests:

- `aria_nbv/aria_nbv/data_handling/_target_selection.py`
- `aria_nbv/tests/data_handling/test_target_selection.py`
- `aria_nbv/aria_nbv/rollouts/dataset_writer.py`
- `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- `aria_nbv/aria_nbv/pose_generation/candidate_mixture.py`
- `aria_nbv/aria_nbv/pose_generation/positional_sampling.py`

High-trust current thesis/design owners:

- `docs/typst/thesis/sections/03-method.typ`
- `docs/contents/theory/candidate_sampling_target_selection.qmd`
- `.agents/memory/state/DECISIONS.md`

Useful but partially stale research artifacts:

- `.agents/work/target-selection-sampling/current-target-selection-audit-2026-06-17.md`
- `.agents/work/target-selection-sampling/01-review-gpt55pro.md`
- `.agents/work/target-selection-sampling/02-review-gpt55pro.md`
- Transcript and goal artifacts for
  `019ed4da-5d8f-7740-a68e-e2ee800d7bee`

Surfaces that still need alignment after the implementation decision:

- `docs/contents/thesis/questions.qmd`
- `.agents/memory/state/OPEN_QUESTIONS.md`
- `.configs/build_rollouts_v1_realistic.toml`
- `.agents/issues.toml`
- `.agents/todos.toml`

## Requirements Distilled

1. V1 target selection is mandatory for thesis-facing results.
2. OBS-SEL owns actor-visible target discovery from detections or model
   predictions. It must not use GT OBBs, GT object IDs, meshes, future renders,
   or oracle RRI as actor-visible target input.
3. PRED-Q conditions on actor-visible target descriptors: OBB geometry, class,
   confidence, projected area, relative pose, semidense support, EVL support,
   and later optional crop descriptors.
4. GT-EVAL owns deterministic matching, labels, invalidity reasons, and
   evaluation metadata after actor-visible target selection.
5. Target-invalid cases such as unmatched, unsupported, or ambiguous targets are
   reason-coded invalid protocol cases, not low-RRI samples.
6. The selector should produce a labelable target pool or set, not a hidden
   single-best-target heuristic.
7. Sampling should be relatively unbiased and simple: uniform or stratified
   sampling across support, projected visibility, distance, class, and
   target-bearing or hard-turn bins.
8. Hard-turn targets are allowed, but they should be controlled through bins or
   stratum caps rather than rejected by default.
9. A single source snippet should be able to produce multiple target-conditioned
   rollout samples when enough valid actor-visible targets are available.
10. Coverage reports must precede scale runs: target count, class histogram,
    support bins, projected-area bins, distance bins, bearing bins, GT match
    status, ambiguity, and selected-vs-eligible breakdown.

## What Has Already Been Tried

Implemented and covered by tests:

- `v1_actor_visible` source order: detected OBBs first, then EVL/backbone
  predicted OBBs; GT-only scenes are refused in V1.
- `v0_gt_target_input` remains an explicit diagnostic or upper-bound mode.
- Hard eligibility based on confidence, support, finite geometry, and optional
  projected visibility.
- Product-style target interest score using confidence, projected visibility,
  support, and support-deficit terms.
- `greedy_top_k` and seeded `temperature_softmax_top_k` selection policies.
- Missing projection fallback visibility score, now a penalty rather than full
  credit.
- Clipped projected-area overlap in image bounds.
- Geometry-only class-compatible GT matching after actor-visible eligibility.
- Ambiguity detection through top1/top2 margin and duplicate predicted-to-GT
  collisions.
- Target lineage and diagnostics persisted into standalone rollout Zarr.
- Streamlit target-audit panel warnings for zero projected-area targets.

Tried or discussed as design alternatives:

- V0 GT OBB target input as diagnostic upper bound.
- V1 observed/predicted target input as thesis default.
- V2 learned observed-target or crop descriptor selection as later escalation.
- Robust target logits instead of raw score products.
- Stratified target sampling as the preferred simple policy.
- Five-family richer candidate sampler as ablation or stress test.
- Three-family candidate sampler as current thesis-core default.

## Current Implementation Facts

The current selector has only two policy enum values:

- `greedy_top_k`
- `temperature_softmax_top_k`

There is no implemented `stratified_uniform` or target-pool sampling policy yet.

Production defaults in `TargetSelectorConfig` include:

- `min_confidence = 0.2`
- `min_projected_area_pixels = 16.0`
- `require_projected_visibility = false`
- `min_support_points = 3`
- `support_saturation_points = 128`
- `missing_projection_visibility_score = 0.35`
- `min_gt_iou = 0.1`
- `gt_ambiguity_margin = 0.02`

The score is a product over actor-visible terms:

- confidence
- projected visibility score
- support score
- support deficit score

GT matching currently uses compatible class plus 3D IoU after eligibility.
Support and projected visibility are not GT-match ranking multipliers in the
current code, even where older docs still imply broader matching.

The rollout writer can iterate selected target rows, but the current realistic
rollout config uses `max_targets_per_sample = 1`, which conflicts with the
newer requirement to get multiple target-conditioned samples from a single
source snippet when feasible.

## Current Issues

### Missing Stratified Target-Pool Policy

The implementation does not yet provide the policy the user converged on:
selecting from a labelable actor-visible target pool with relatively uniform or
stratified sampling. The existing `greedy_top_k` and `temperature_softmax_top_k`
remain useful baselines, but they should not be the thesis default.

### Zero Projected-Area Label-Valid Targets

The prior audit found selected label-valid targets with
`target_projected_area_pixels == 0.0` in probe rollouts. This is not necessarily
a bug if 3D support makes the target actor-visible, but it must become an
explicit stratum or diagnostic outcome. It should not be silently mixed with
well-projected observed targets.

### Zero-Score Saturated Tie Selection

Saturated targets can receive exactly zero score because the support-deficit
term goes to zero. If there are not enough positive-score eligible rows,
deterministic greedy ranking can still select zero-score targets by source/order
tie. This is another reason to separate eligibility, stratification, and
sampling from a scalar score.

### No Hard-Turn Bin Contract

The code records target-bearing diagnostics for candidate generation, but target
selection does not yet classify actor-visible targets into turn-angle bins. The
transcript discussion suggests allowing hard turns through bins such as:

- `front`: theta <= 45 degrees
- `side`: 45 < theta <= 100 degrees
- `hard_turn`: theta > 100 degrees

The angle should be computed from the current/reference pose forward direction
to the actor-visible OBB center, not from GT state.

### Multiple Targets Per Source Is Not Enabled By Default

The user explicitly wanted multiple target-conditioned samples from a source
snippet. `.configs/build_rollouts_v1_realistic.toml` currently sets
`max_targets_per_sample = 1`, so even a good pool policy would be underused in
that default config.

### Docs And Code Still Disagree On GT Matching

`docs/contents/thesis/questions.qmd` still describes a broader matching rule
with compatible class, OBB IoU, visibility/support, projected area, semidense,
EVL support, and a compact score. Current code and tests use actor-visible
eligibility first and geometry-only GT matching afterward. The current
implementation is the cleaner variant because it avoids mixing selection
reliability with GT identity matching.

### Candidate Sampler Defaults Are Split

The code and theory page now describe a three-family default candidate sampler:

- `forward_local`
- `target_bearing_local`
- `lateral_target_bypass`

The realistic rollout config still contains a five-family mixture with local
refinement and revisit/backtrack components. That may be valid as an ablation or
stress config, but it should not silently contradict the thesis-core default.

### Audit Reporting Is Not Yet Scale-Gate Quality

The current target-audit panel and persisted fields are useful, but the scale
gate needs a stable report with row counts and histograms across target bins,
selected-vs-eligible breakdowns, label-valid rates, unmatched/ambiguous rates,
and per-stratum support.

## Stale Or Superseded Findings

The older `01-review-gpt55pro.md` and `02-review-gpt55pro.md` notes contain
useful design critique, but several concrete bug claims are no longer current:

- `position_id` persistence is implemented and tested.
- Projected area is clipped to image bounds.
- Missing projection no longer receives full visibility credit by default; it
  receives the configured fallback penalty.
- The helper tests sometimes use `min_support_points = 1`, but production
  config defaults to `3`.
- GT leakage through normal V1 source selection was not found in the current
  implementation.

## Recommended Rework

### 1. Add `stratified_uniform` Target Selection

Add a new `TargetSelectionPolicy.STRATIFIED_UNIFORM` that:

- builds an eligible actor-visible target pool;
- computes per-target strata;
- samples non-empty strata uniformly or with configurable caps;
- samples targets uniformly within the selected stratum;
- stores `stratum_key`, band fields, sampling probability, and policy metadata.

The existing score should remain available as diagnostics and as a comparison
baseline, not as the default target data-collection objective.

### 2. Add Explicit Target Strata

Suggested initial fields:

- support band: `barely_supported`, `medium`, `saturated`
- projected-area band: `none_or_3d_only`, `small`, `clear`
- distance band: `near`, `mid`, `far`
- turn bin: `front`, `side`, `hard_turn`
- class bucket: semantic class or `unknown`
- source family: detected, EVL/backbone prediction, or V0 diagnostic

Keep bins coarse and auditable. The goal is coverage, not a learned selector.

### 3. Preserve Hard-Turn Targets Through Bins

Do not reject hard-turn targets by default. Instead:

- compute a horizontal turn angle from reference pose forward to the
  actor-visible target center;
- bin it as front/side/hard-turn;
- cap or report the hard-turn stratum separately;
- compare performance and label validity by turn bin.

### 4. Enable Multiple Target-Conditioned Samples Per Source

Change rollout config and writer behavior only after the pool policy exists:

- allow `max_targets_per_sample > 1` in the relevant rollout config;
- keep deterministic target row IDs and lineage;
- ensure repeated source snippets with different targets remain separable in
  `rollouts.zarr`.

### 5. Keep GT Matching Simple

Keep the current deterministic GT matching contract:

- semantic compatibility;
- 3D IoU threshold;
- top1/top2 ambiguity margin;
- duplicate predicted-to-GT ambiguity handling.

Do not reintroduce support or projected visibility as GT-match score terms
unless an audit demonstrates concrete identity-matching failures that 3D IoU
and ambiguity checks cannot handle.

### 6. Add A Target-Selection Coverage Report

Before scale rollout generation, add or extend a report that emits:

- source count and eligible target count;
- selected target count;
- label-valid, unmatched, ambiguous, unsupported, and no-projection counts;
- histograms over support, projected area, distance, class, and turn bins;
- selected-vs-eligible breakdown per stratum;
- zero-score eligible count;
- zero projected-area selected count;
- GT IoU and ambiguity-gap summary for label-valid targets.

This report should become the gate for choosing threshold profiles and whether
to require projected visibility for any thesis subset.

### 7. Align Current Docs After Code

After implementing the policy, update:

- `docs/typst/thesis/sections/03-method.typ`: make stratified target-pool
  sampling a first-class V1 protocol, not a later aside.
- `docs/contents/theory/candidate_sampling_target_selection.qmd`: add the
  concrete bins and default policy.
- `docs/contents/thesis/questions.qmd`: replace stale broad GT-matching prose
  with actor-visible eligibility plus geometry-only GT matching.
- `.agents/memory/state/DECISIONS.md`: add the chosen target-pool sampling
  default.
- `.agents/memory/state/OPEN_QUESTIONS.md`: retire already-decided matching
  questions or narrow them to concrete ambiguity-threshold tuning.
- `.configs/build_rollouts_v1_realistic.toml`: reconcile target count per
  source and three-family vs five-family candidate mixture naming.

## Implementation Sketch

Data model additions:

- `TargetSelectionPolicy.STRATIFIED_UNIFORM`
- `TargetSelectionConfig.stratify_by`
- `TargetSelectionConfig.turn_bin_degrees`
- `TargetSelectionConfig.support_bins`
- `TargetSelectionConfig.projected_area_bins`
- `TargetSelectionConfig.distance_bins`
- `TargetSelectionConfig.max_per_stratum`
- `TargetCandidateRow.stratum_key`
- `TargetCandidateRow.support_band`
- `TargetCandidateRow.projected_area_band`
- `TargetCandidateRow.distance_band`
- `TargetCandidateRow.turn_bin`

Selection algorithm:

1. Resolve actor-visible target source.
2. Build eligible rows and diagnostics exactly as today.
3. Compute coarse bins from actor-visible row fields.
4. Group eligible rows by stratum key.
5. Choose strata in deterministic seeded order without replacement.
6. Choose one or more rows uniformly within each chosen stratum.
7. Run GT-EVAL matching after selection.
8. Persist policy, stratum, probability, and reason-code metadata.

Testing priorities:

- deterministic seeded stratified sampling;
- hard-turn bin computation from actor-visible OBB center;
- zero projected-area targets are either separate stratum or rejected only when
  `require_projected_visibility = true`;
- saturated zero-score targets no longer dominate or accidentally tie-select;
- multiple targets per source are persisted with distinct target IDs;
- GT-only V1 refusal remains unchanged;
- geometry-only GT matching remains unchanged;
- rollout Zarr and inspection surfaces include new stratum fields.

## Verification Plan For The Implementation Pass

Targeted package tests:

```bash
cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py
cd aria_nbv && uv run pytest tests/rollouts/test_dataset_writer.py tests/rollouts/test_zarr_store.py
```

Docs and memory checks after narrative changes:

```bash
make qmd-frontmatter-check
make check-agent-memory
cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-main.pdf
```

Recommended audit before scale runs:

```bash
make kg-claim-check KG_CLAIM="V1 target selection samples actor-visible labelable target pools with stratified support, projected-area, distance, class, and bearing bins; GT objects are used only for post-selection labels and evaluation."
```

## Canonical Updates Needed

The research points to these future changes, but this iteration did not patch
them:

- implement stratified target-pool sampling in
  `aria_nbv/aria_nbv/data_handling/_target_selection.py`;
- add tests in `aria_nbv/tests/data_handling/test_target_selection.py`;
- persist stratum metadata in rollout writer/store/inspection surfaces;
- update `docs/typst/thesis/sections/03-method.typ`;
- update `docs/contents/theory/candidate_sampling_target_selection.qmd`;
- update `docs/contents/thesis/questions.qmd`;
- update `.agents/memory/state/DECISIONS.md` and
  `.agents/memory/state/OPEN_QUESTIONS.md`;
- reconcile `.configs/build_rollouts_v1_realistic.toml`;
- update backlog entries once implementation scope is known.
