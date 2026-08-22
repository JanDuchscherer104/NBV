---
id: 2026-08-22_factual_selected_family_trajectory_view
date: 2026-08-22
title: "Factual selected-family trajectory view"
status: done
topics: []
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fffa4-b85c-7db1-8404-d69c73e6485e
repo_branch: codex/rollout-supervision-inspection-refresh
repo_head: e1945d1f1cd6541cde332ddaa7f3ef0a22878ba5
repo_object_format: sha1
worktree_kind: linked
---

## Task
Replace the non-interpretable singleton selected-family sequence endpoint plot with factual trajectory and endpoint views.

## Method
Read the validated promoted pilot shard through `candidate_population_evidence`, then retain its factual trajectory identity rather than aggregating the one-rollout exact cohorts.

## Findings
The pilot has four H=8 factual trajectories, one per exact temperature cohort, and therefore every previous sequence median/IQR had `n=1`. The panel now renders one categorical heatmap cell per persisted selected action and one unaggregated endpoint marker per trajectory in `aria_nbv/aria_nbv/app/panels/_stored_rollouts/reconstruction_return.py`. Focused tests cover factual acquisition expansion and marker-only endpoint rendering in `aria_nbv/tests/app/panels/test_stored_rollouts_candidate_choice.py`.

## Verification
Passed `uv run --project aria_nbv pytest -q aria_nbv/tests/app/panels/test_stored_rollouts_candidate_choice.py` (4 passed), the related panel suites (41 passed), Ruff format/check, `compileall`, and `git diff --check`. A real promoted-store smoke produced 4 trajectory rows, 32 factual heatmap cells, and four endpoint markers at T={0.5, 1, 2, 4}.

## Canonical Owner Impact
Python inspection presentation and focused panel tests only; no schema, generation, training, or Typst notation change.
