---
id: 2026-08-22_pool_candidate_choice_evidence_across_temperatures
date: 2026-08-22
title: "Pool candidate choice evidence across temperatures"
status: done
topics: []
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
---

## Task
Replace the misleading temperature-stratified, one-trajectory selected-family heatmap with pooled factual candidate-choice shares and conditional transitions.

## Method
Projected candidate dynamics from validated rollout artifacts, then recomputed per-step family fractions and next-step transitions directly from factual states. Pooled temperature/cohort strata only after retaining the policy, horizon, branch-factor, and beam-width contract.

## Findings
`aria_nbv/aria_nbv/rollouts/inspection.py` now exposes pooled candidate-choice summary and transition rows. `aria_nbv/aria_nbv/app/panels/_stored_rollouts/candidate_generation.py` renders their per-step share plot and expected-versus-observed transition plots; `reconstruction_return.py` no longer renders the unrelated per-trajectory heatmap. The drill-down disclosure is owned by `validity_support.py`.

## Verification
Passed: `uv run --project aria_nbv pytest -q aria_nbv/tests/rollouts/test_inspection.py aria_nbv/tests/app/panels/test_stored_rollouts_candidate_choice.py aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py aria_nbv/tests/app/panels/test_stored_rollouts_theory.py` (172 passed). Passed Ruff format/check, `python -m compileall`, and `git diff --check` on the changed lane.

## Canonical Owner Impact
Python and test owners only; no schema, configuration, generation, training, or Typst-owner change.
