---
kind: plan
status: proposed
depends_on:
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/185
tracks:
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/54
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/69
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/70
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/71
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/72
  - https://github.com/JanDuchscherer104/ARIA-NBV/issues/120
---

# Candidate-generation autoresearch after Issue #185

## Outcome

Evaluate and improve candidate realism only after the
[Issue #185 refactor](https://github.com/JanDuchscherer104/ARIA-NBV/issues/185)
has established its new candidate and rollout interfaces. This plan does not
modify that architecture stack and does not authorize large-scale generation.

## Requirements summary

1. The active Issue #185 task owns module boundaries, immutable candidate
   requests/results, center/gaze composition, admission evidence, presentation
   adapters, persistence adapters, and rollout state projection.
2. This follow-up owns only post-refactor scientific behavior and evidence:
   horizon-aware inspection, candidate-support reliability, orbit standoff
   variation, and—if justified by results—step-conditioned family allocation.
3. Do not add a parallel generator interface, schedule abstraction, plotting
   owner, admission pipeline, or persistence adapter. Use the interfaces landed
   by Issue #185.
4. Preserve the canonical full candidate shell, including invalid rows and
   their provenance. The current result contract explicitly keeps full-shell
   masks and provenance separate from compact valid views
   (`aria_nbv/aria_nbv/pose_generation/types.py:201-225`).
5. Preserve actor/Oracle separation and the production nonzero view-jitter
   invariant. The active mixture rejects zero resolved azimuth or elevation
   jitter (`aria_nbv/aria_nbv/pose_generation/candidate_mixture.py:187-209`).
6. Keep each implementation PR limited to one testable scientific hypothesis.
   Negative or inconclusive experiments remain evidence and are not promoted
   into production configuration.

## Dependency gate

Before starting implementation:

1. Wait until the Issue #185 refactor stack is merged to `main`; do not edit or
   restack its branches while its task is active.
2. Record the resulting `origin/main` SHA and re-resolve every path named below.
   The current paths are evidence of responsibility, not promises about the
   post-refactor layout.
3. Run the refactor's exact-parity and replay golden checks. Candidate rows,
   masks, provenance, seeds, selections, and stored scientific values must still
   match its frozen baseline.
4. If parity fails, stop this plan. Repair the structural refactor before
   interpreting any behavioral experiment.
5. Re-run the current candidate-quality baseline on matched real roots and
   seeds. Use that post-refactor run as the control for every work package.

## Work packages

### WP1 — Make horizon and family behavior inspectable

Create a visualization-only PR through the presentation owner landed by Issue
#185.

- Add compact rollout context to candidate-support titles: planned horizon
  `H`, factual step `t`, and remaining budget where available.
- Plot proposed, actor-valid, and selected support by family and step without
  dropping zero-support states.
- Add orbit-specific target-relative diagnostics for azimuth progress and
  normalized standoff radius.
- Distinguish three claims in labels and captions: proposal coverage, chainable
  motion-feasible coverage, and the selected rollout path. A horizon-eight
  proposal can expose broad azimuth support without proving that the policy
  selected a full orbit.
- Keep all plot inputs factual and persisted; missing geometry stays unavailable
  rather than becoming zero.

Acceptance criteria:

- A stored `H=8` rollout displays `H`, `t`, and remaining budget consistently.
- A state with an applicable family and zero valid rows remains visible.
- Proposed, actor-valid, and selected counts reconcile with the full-shell row
  counts.
- Plot-only changes leave candidate tensors and stored data unchanged.

### WP2 — Test bounded refill against family collapse

Implement the smallest candidate-support experiment through the post-refactor
candidate program and admission result. This addresses
[Issue #71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71) and feeds
the preflight in [Issue #54](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54).

- Compare the fixed-attempt control with a bounded per-family proposal
  reservoir on matched real roots and seeds.
- Retain exact family provenance for every attempted row; do not silently
  replace a collapsed target-relative family with forward-local rows.
- Stop after a configured attempt budget and return explicit insufficient
  support when the requested valid support cannot be reached.
- Keep total admitted candidate budget and downstream scoring compute equal in
  control and treatment.

Acceptance criteria:

- No unbounded resampling path exists.
- Applicable-family collapse is explicit and machine-testable.
- The treatment does not change view-jitter bounds, actor inputs, admission
  thresholds, or scoring compute.
- Promote only if the primary support gate improves without worse hard
  feasibility, provenance, determinism, or throughput gates.

### WP3 — Test variable-standoff target orbit

Implement one center-family experiment through the closed center configuration
landed by Issue #185. The current target-orbit implementation fixes every
candidate to the root's horizontal target standoff
(`aria_nbv/aria_nbv/pose_generation/positional_sampling.py:129-172`).

- Compare fixed standoff with a small, bounded set or distribution of target
  standoffs expressed relative to the factual root-target distance.
- Preserve bilateral angular proposals and let existing admission criteria
  decide endpoint and transition feasibility.
- Keep center choice separate from gaze choice. “Radial-away” gaze is a view
  variant at a center, not a second positional family; test it only as a paired
  gaze variant if it answers a concrete framing hypothesis.
- Measure proposed azimuth coverage, chainable azimuth progress, target framing,
  collision/motion rejections, and admitted support. Do not use selected-path
  coverage as the sole proposal-quality metric.

Acceptance criteria:

- Fixed and variable-standoff controls use matched roots, seeds, attempt
  budgets, and admitted candidate budgets.
- Configured standoff bounds are visible in plots and testable from provenance.
- Every admitted transition passes the unchanged feasibility contract.
- Promote only a bounded setting that improves support or framing without
  material regression in hard gates or throughput.

### WP4 — Test step-conditioned family allocation only after WP2–WP3

Use the rollout-owned node-to-request projection from Issue #185. Do not add a
second scheduling control plane.

- Compare the static mixture with one deliberately simple phase schedule, such
  as early approach, middle orbit/standoff, and late refinement.
- Allow different family parameters at different steps only through an
  immutable resolved candidate profile recorded with the rollout.
- Preserve the static resolver as the control and default.
- Defer a general schedule protocol until a second real implementation requires
  variation; Issue #185 explicitly owns that architectural decision.

Acceptance criteria:

- The same rollout state, profile, proposal replica, and seed reproduce the same
  candidate table.
- Different phase allocations are visible by step in WP1 plots and persisted
  provenance.
- The schedule cannot access Oracle labels, RRI, future state, or selected
  outcomes from the current expansion.
- Promote only if it improves the same frozen primary metric while every hard
  gate remains satisfied.

## Experiment contract

Every behavioral PR uses:

- the same small real-root cohort and proposal replicas for control and
  treatment;
- one declared primary metric plus hard gates for actor safety, feasibility,
  deterministic replay, family collapse, support count, and throughput;
- exact configuration, code SHA, seeds, root IDs, and persisted plot inputs;
- GPU execution for candidate evaluation/rendering where supported, while
  reporting device and wall-clock time;
- a result table that includes failed and unavailable states rather than only
  successful rollouts.

The broad-generation gate in
[Issue #120](https://github.com/JanDuchscherer104/ARIA-NBV/issues/120) remains
closed until these small controls are complete and their retained deltas are
re-evaluated together.

## PR sequence

1. `WP1`: visualization and evaluator observability only.
2. `WP2`: bounded support/refill experiment.
3. `WP3`: variable-standoff orbit experiment.
4. `WP4`: optional phase schedule, only if WP2 or WP3 provides a retained
   behavior worth scheduling.

Each PR targets the latest required predecessor, contains its own tests and
plots, and is independently reviewable. After every work package, rebase the
next branch onto the accepted predecessor, run exact-head CI, answer and resolve
all valid review threads, and stop the stack when an experiment has no positive
delta.

## Risks and mitigations

- **Architecture overlap:** wait for Issue #185 and use only its public seams.
- **Stale baselines:** regenerate the control after the refactor merges.
- **Aggregate metrics hide collapse:** gate per root, step, and applicable
  family before aggregating.
- **Orbit support is mistaken for human motion:** report proposed, chainable,
  and selected coverage separately.
- **Schedule complexity arrives early:** keep WP4 optional and retain one static
  default.
- **Stacked-PR churn:** begin only after the refactor stack is on `main`, then
  keep this stack linear and short.

## Verification

For every retained work package:

1. Run focused candidate-generation and rollout tests for the changed contract.
2. Run replay/Oracle golden parity and deterministic fixed-seed checks.
3. Run Ruff and mypy on the touched package owners.
4. Generate the WP1 plots from the matched real-data control and treatment.
5. Verify the PR's exact head SHA in hosted CI.
6. Re-query mergeability and unresolved review threads before declaring the PR
   ready.

## Stop condition

The plan is complete when the Issue #185 refactor is preserved, WP1 makes the
evidence auditable, and every promoted behavioral change has a matched-control
positive delta with all hard gates satisfied. No work package in this plan
authorizes the larger-scale generation governed by Issue #120.
