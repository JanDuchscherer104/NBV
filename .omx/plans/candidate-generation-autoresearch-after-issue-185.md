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

## Ownership

The active Issue #185 task owns module boundaries and interfaces. Agents-DB
records `issue-020` and `todo-028` own the durable candidate-quality backlog,
acceptance criteria, and verification. This document only sequences their work
after the refactor; it does not create another generator, schedule, plotting,
admission, or persistence owner.

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

## Execution sequence

### WP1 — Make horizon and family behavior inspectable

Create a visualization-only PR through the presentation owner landed by Issue
#185. Add `H`, factual step, and remaining budget to support plots; show
proposed, actor-valid, and selected family support; and distinguish proposed,
chainable, and selected orbit coverage.

### WP2 — Test bounded refill against family collapse

Implement the smallest candidate-support experiment through the post-refactor
candidate program and admission result. This addresses
[Issue #71](https://github.com/JanDuchscherer104/ARIA-NBV/issues/71) and feeds
the preflight in [Issue #54](https://github.com/JanDuchscherer104/ARIA-NBV/issues/54).

Compare fixed attempts with a bounded per-family reservoir on matched real
roots and seeds. Preserve attempted-row provenance, fixed downstream scoring
compute, explicit insufficient-support outcomes, and the seminar jitter and
actor-safety invariants.

### WP3 — Test variable-standoff target orbit

Implement one center-family experiment through the closed center configuration
landed by Issue #185. The current target-orbit implementation fixes every
candidate to the root's horizontal target standoff
(`aria_nbv/aria_nbv/pose_generation/positional_sampling.py:129-172`).

Compare fixed standoff with one bounded relative-standoff treatment on matched
roots, seeds, and budgets. Preserve bilateral proposals and unchanged admission.
Treat radial-away/towards as paired gaze variants, not positional families.

### WP4 — Test step-conditioned family allocation only after WP2–WP3

Use the rollout-owned node-to-request projection from Issue #185. Do not add a
second scheduling control plane.

Only after a retained behavior needs scheduling, compare the static mixture
with one simple phase schedule through the rollout-owned resolved profile. Keep
the static resolver as default and do not introduce a general schedule protocol.

## PR sequence

1. `WP1`: visualization and evaluator observability only.
2. `WP2`: bounded support/refill experiment.
3. `WP3`: variable-standoff orbit experiment.
4. `WP4`: optional phase schedule, only if WP2 or WP3 provides a retained
   behavior worth scheduling.

Each PR is independently reviewable. A negative or inconclusive result discards
only that experiment; WP3 continues from the last accepted baseline even when
WP2 is rejected. WP4 runs only when WP2 or WP3 produces retained behavior.

## Verification

For every retained work package:

Use the criteria and commands in `todo-028`. Every behavioral comparison uses
matched real roots and seeds, one primary metric plus hard gates, GPU execution
where supported, persisted plots, exact-head CI, and zero unresolved review
threads.

## Stop condition

The plan is complete when the refactor is preserved, WP1 makes the evidence
auditable, and every promoted change has a matched-control positive delta with
all `todo-028` gates satisfied. Issue #120 remains the sole scale-up gate.
