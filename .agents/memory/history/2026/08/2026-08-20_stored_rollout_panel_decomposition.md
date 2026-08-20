---
id: 2026-08-20_stored_rollout_panel_decomposition
date: 2026-08-20
title: "Stored rollout panel decomposition"
status: done
topics: [streamlit, rollout-inspection, codebase-design]
confidence: high
canonical_updates_needed: []
---

## Task

Decompose the monolithic stored-rollout Streamlit page while preserving its current four-tab, validated, lazy read-only workflow.

## Method

Used the historical PR #38 module names only as a navigation reference, then partitioned current code by current ownership: cache/read-model boundary, overview/topology, reconstruction, candidate provenance, target validity, Q_H, failure triage, drill-down/Rerun, and shared widgets. Graphify was unusable for this worktree, so exact current sources were the authority.

## Findings

`_stored_rollouts_page.py` is now a 148-line coordinator. The private `_stored_rollouts/` package owns the separated presentation concerns. No rollout schema, reporting semantics, generation behavior, dependencies, or public page entry point changed. Focused tests now import the private owner under test instead of treating the former monolith as an internal API.

## Verification

Passed `pytest -q tests/app/panels/test_counterfactual_rollouts_panel.py tests/app/panels/test_stored_rollouts_projection_laziness.py tests/app/test_app_router.py` (79 tests), Ruff format/check, `python -m compileall` for the changed panel modules, and `git diff --check`.

## Canonical Owner Impact

- `aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py`
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- `aria_nbv/tests/app/panels/test_stored_rollouts_projection_laziness.py`
