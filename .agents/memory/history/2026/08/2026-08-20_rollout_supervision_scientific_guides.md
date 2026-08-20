---
id: 2026-08-20_rollout_supervision_scientific_guides
date: 2026-08-20
title: "Rollout Supervision scientific guides and task-first navigation"
status: done
topics: [streamlit, rollout-inspection, scientific-communication, lazy-ui]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/shared.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/overview_topology.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/reconstruction_return.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/validity_support.py
---

## Task

Replace the overloaded flat rollout-inspection popovers with reader-intent scientific guidance, remove redundant navigation layers, and prevent target-score correlation from presenting unsupported evidence.

## Method and findings

Historical PR #38 supplied modular/lazy architectural precedent but not a superior explanatory guide implementation. The final surface uses one existing renderer seam with a concise visible answer and an `Interpret this plot` popover. Every primary guide now states its interpretation, visual encoding, uncertainty, definition, and relevant source. Target admission and Q_H masks cite their owning strict-IoU/V1 contracts rather than the RRI equation.

Rollout Supervision now uses four task routes. Its diagnostic route conditionally selects failure triage or inspection/export/Rerun, retaining invalid-store gates and avoiding eager expensive evidence reads. Pairwise correlation uses finite pair-local observations, explicit support/reason metadata, and does not render a heatmap when no finite off-diagonal estimate exists.

## Verification

Product commits: `643a6f776c`, `a7bda7036c`, `602d07acb0`, `11a9cf8d40`, and `a0748157b1`.

The final focused AppTest suite collected 95 tests and passed. Ruff format/check, compileall, and `git diff --check` passed. The changed-files cleaner found no safe simplification. Independent code review approved the final head and the independent architecture audit cleared presentation-only scope, guide completeness, correlation sufficiency, and lazy diagnostic dispatch.

## Canonical-state impact

No reader, reducer, schema, campaign-generation, training, dependency, or Rerun-control contract changed. The untracked research and plan artifacts under `.omx/` remain workflow evidence rather than product truth.
