---
id: 2026-08-20_rollout_streamlit_cache_refresh
date: 2026-08-20
title: "Rollout Streamlit Cache Refresh"
status: done
topics: [streamlit, rollouts, caching]
confidence: high
canonical_updates_needed: []
---

## Task

Add one explicit, safe refresh action for cached read-only rollout and Q_H
inspection results in both Streamlit pages.

## Method

Kept the existing replacement-sensitive artifact identities as cache keys,
completed the existing inspector clear path, and added a lazy cross-page clear
hook rather than a new cache backend or persistent cache.

## Findings

- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py` now clears the
  candidate-population cache and coordinates both page families.
- `aria_nbv/aria_nbv/app/panels/training_dataset.py` clears its summary, deep
  scan, readiness, preview, and session-local results.
- Both pages expose **Refresh rollout caches**.
- `aria_nbv/tests/app/panels/test_training_dataset_panel.py` proves the
  unified clear reaches every training-page cache family.

## Verification

- `uv run pytest -q tests/app/panels/test_training_dataset_panel.py
  tests/app/panels/test_counterfactual_rollouts_panel.py` — 61 passed.
- Ruff format check and Ruff check passed.
- `python -m compileall` for changed modules and `git diff --check` passed.

## Canonical Owner Impact

Python presentation/cache owners and their focused test owner were updated; no
schema, configuration, training, or campaign-generation owner changed.
