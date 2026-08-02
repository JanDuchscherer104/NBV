# Critic Review: Thin Root/Nested AGENTS Rewrite — Iteration 1

Date: 2026-08-01

Verdict: **ITERATE**

The vertical-slice/atomic-merge design is sound and consistent with the accepted
target. Alternatives, concurrency ownership, deterministic CI, disposable
native trials, ADR, staffing, Team verification, goal-mode guidance, and Ralph
fallback are present. Execution readiness still needs five corrections.

## Required corrections

1. Add a compact assertion-disposition contract for the current routing/G002
   evidence: current assertion family, retain/replace/remove decision, exact
   target JSON/assertion behavior, and positive/negative probe. “Candidate-
   independent” must be executable without inventing a new framework.
2. Define an untracked disposable `prompt-set-v1` artifact format during WP1,
   including six literal prompts, per-scenario expected locators/commands,
   forbidden outcomes, and boolean rubric rows. Do not add a checked-in runner.
3. Create `$trial_root/evidence` before any S6 redirect.
4. Make proof order explicit: pre-removal proof validates the destination and
   consumer intermediate; only the repeated post-removal proof closes a slice.
5. Correct control-plane metadata: final Architect review path/status, debrief
   identity/lifecycle, and installed role reasoning defaults (`executor` and
   `test-engineer` are medium by catalog).

Approval requires these corrections while retaining the no-new-evaluator-
bureaucracy boundary and removing executor discretion from acceptance criteria
2, 9, and 10.
