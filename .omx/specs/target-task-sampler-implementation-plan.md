# Target-Task Sampler Implementation Plan

## Summary

Replace the stale actor-visible target-selection contract with an oracle
target-task sampler for rollout data generation. Target selection belongs to
the oracle/data-generation pipeline; the learned model is target-conditioned
view selection. The first implementation should prioritize simple, auditable
target-task labels over learned or deployable automatic target discovery.

## Key Changes

- Add an oracle target-task sampler mode in the target-selection/data-generation
  surface. It should admit target tasks by configured 3D OBB IoU and ambiguity
  margin against GT targets, not by RGB projection, class correctness,
  confidence, semidense support, or EVL support.
- Use moderate defaults for the identity gate: start with
  `min_identity_iou = 0.25` and `identity_ambiguity_gap = 0.05`, and report
  coverage sweeps for loose/moderate/strict thresholds before scale runs.
- Select a capped multi-target set per source snippet with seeded uniform
  sampling from identity-valid targets. Default planned cap: `3` targets per
  snippet unless a storage estimate shows `4` is still safe.
- Persist all selected identity-valid target tasks even when measured headroom
  is low. Compute target root error, candidate gains, max candidate gain, and
  headroom band after oracle candidate evaluation; use loaders or evaluation
  filters to choose positive-headroom subsets.
- Keep class, confidence, current RGB projection, semidense support, EVL
  support, target distance, and target bearing as descriptor/audit fields.
  They may define later subsets, but they are not first-pass eligibility gates.
- Preserve the existing actor-visible selector only as legacy/diagnostic code
  unless a later task explicitly revives deployable target discovery.

## Code Surfaces

- Target selection/data handling: introduce the oracle target-task sampler
  config, identity assignment, threshold sweep diagnostics, and seeded uniform
  cap behavior.
- Rollout writer/store/inspection: persist identity IoU, ambiguity gap,
  selected-target rank/cap metadata, cheap diagnostics, target root error,
  candidate gain/headroom summaries, and headroom band.
- Configs: update the realistic rollout config away from single-target
  `max_targets_per_sample = 1` toward the capped multi-target default.
- Tests: add deterministic tests for identity-valid matching, ambiguity
  rejection, seeded uniform cap selection, threshold sweep reporting, and
  headroom persistence/filtering.

## Current-Truth Repairs

- Update `docs/typst/thesis/sections/03-02-data-generation.typ` as the active
  thesis owner for the data-generation target-task protocol.
- Update `docs/contents/thesis/questions.qmd`, `docs/contents/thesis/roadmap.qmd`,
  and `.agents/memory/state/{DECISIONS.md,OPEN_QUESTIONS.md,PROJECT_STATE.md}`
  so they no longer state that automatic actor-visible target selection is the
  main thesis result.
- Update or retire older backlog entries that describe target selection as
  actor-visible OBS-SEL. Keep any actor-visible selector follow-up explicitly
  marked as future/diagnostic.
- Update stale shared target-match equations if they still multiply GT identity
  matching by class/support/projection. The current target-task identity gate
  should be geometry-first 3D IoU plus ambiguity margin; class and support are
  diagnostics/subsets.

## Verification

- `cd aria_nbv && uv run pytest tests/data_handling/test_target_selection.py`
- `cd aria_nbv && uv run pytest tests/rollouts/test_dataset_writer.py tests/rollouts/test_zarr_store.py`
- `make qmd-frontmatter-check`
- `make check-agent-memory`
- `cd docs && typst compile typst/thesis/main.typ --root . /tmp/thesis-main.pdf`
- `rg -n "actor-visible target selection|OBS-SEL|PRED-Q|GT-EVAL|support/projection.*match|target-interest ranking" docs .agents aria_nbv`

## Assumptions

- Target-task selection is an oracle/data-generation operation, not a learned
  deployable target-discovery claim.
- GT may be used to choose labelable target tasks because the oracle pipeline is
  allowed to define supervision.
- The thesis claim is target-conditioned finite-candidate view selection under
  oracle-selected target tasks.
- Low-headroom targets are evidence and should be stored; filtering belongs in
  training/evaluation, not first-stage target-task admission.
