---
id: 2026-08-21_stored_rollout_session_cache_plot_restoration
date: 2026-08-22
title: "Stored-rollout session cache and scientific plot restoration"
status: done
topics: [streamlit, session-cache, rollout-inspection, scientific-visualization]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a023ce-d7cb-7552-9936-6255e3485e9f
files_touched:
  - .omx/plans/prd-stored-rollout-session-cache-seam.md
  - .agents/memory/history/2026/08/2026-08-21_stored_rollout_session_cache_plot_restoration.md
---

## Task

Execute the approved stored-rollout session/cache plan and restore the lost
scientific candidate-support inspection views, while preserving lazy reads,
domain ownership, persistence, generation, training, CLI, report, and Rerun
boundaries.

## Final result

The implementation is complete on exact tracked HEAD
`101c713d8136ee4380be7f4c008b1136cd5252c0`.

The accepted G007, G008, and G009 follow-ups are reflected in the plan:

- G007 repaired the discounted-return session call, kept normalized geometry
  bounded and default-visible, made lower-grain selection exact, preserved
  shell and unit distinctions, and expanded the existing scientific
  explanation owner with canonical references.
- G008 completed canonical equation/source ownership for temporal gain, RRI,
  selection, target-view, collision/clearance, candidate-family, and mask
  explanations, with exhaustive/fail-closed reference mapping.
- G009 corrected the remaining collision applicability/evaluation/denominator
  reference to the inspection-code owner and added the focused UI regression.

No new projection framework, schema, dependency, service, generation path,
training behavior, CLI/report format, or Rerun control was added.

## Verification

- **Focused tests:** 212 passed across the final inspection, panel, laziness,
  CLI, reporting, and reference-ownership suites.
- **Static checks:** Ruff format/check passed for all 10 changed branch files;
  compileall passed for the five changed product modules; `git diff --check`
  passed.
- **CLI probe:** `nbv-rollouts-info --help` passed.
- **Cleanup:** changed-files `ai-slop-cleaner` was a no-op; post-cleaner
  verification remained green.
- **Independent review:** code reviewer `APPROVE`; architect `CLEAR`; no P0,
  P1, or P2 findings remained on the exact final HEAD.
- **Typing context:** targeted mypy remained an informational baseline with
  282 pre-existing errors; it was not used as evidence of a regression or as
  a claim of full-package cleanliness.
- **Graphify:** the projection-owner worktree status remained unavailable,
  so Graphify was unusable. The final audit used exact current sources and
  focused tests instead.
- **External state:** no push, pull request, issue, review, or other external
  GitHub write was performed.

## Artifact status

The implementation commits are tracked. The following diagnostic/planning
artifacts remain intentionally untracked in the worktree and were not added to
the product diff:

- `.omx/plans/prd-stored-rollout-session-cache-seam.md`
- `.omx/context/stored-rollout-session-cache-seam-20260821T101909Z.md`
- this dated debrief

The plan now marks G007 and G008 complete and records the accepted G009
reference-only correction. The historical G004/G005 review-blocked entries
remain preserved in the Ultragoal ledger; their resolver chain is the evidence
for the final repaired state and is not rewritten here.

## Canonical-state impact

This debrief records the final exact-head evidence and the documentation-only
plan corrections. It does not alter tracked Python, tests, the runtime ledger,
or the Ultragoal context.
