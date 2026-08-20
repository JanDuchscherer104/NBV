---
id: 2026-08-20_corpus_rollout_quality_context
date: 2026-08-20
title: "Corpus rollout quality context"
status: done
topics: [rollouts, reporting, streamlit]
confidence: high
canonical_updates_needed: []
---

## Task
Make the corpus rollout-supervision view explain its selection quality without obscuring factual data or changing generation.

## Method
Read the validated V10 pilot shard, trace its persisted selected-step gains into the corpus temporal report, and keep the UI change inside the existing reporting and presentation seams.

## Findings
- The selected V10 rich-profile shard has a near-zero first selected-view gain in all four temperature trajectories, followed by an approximately 0.423% gain at the second acquisition. This is persisted evidence, not a zero-filled chart.
- `aria_nbv/aria_nbv/rollouts/reporting.py` now includes factual selected gain, selection probability, and entropy in the compatible corpus temporal summary; physical selected paths, rather than content IDs, count corpus shards.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/reconstruction_return.py` displays one-based acquisition numbers, essential root-gain plots, compact selection-quality cards, and an interpretation popover; optional RRI/distribution tables remain collapsed.

## Verification
- `aria_nbv/.venv/bin/pytest -q aria_nbv/tests/rollouts/test_reporting.py --junitxml=/tmp/aria-nbv-reporting-20260820-qa.xml` — 29 passed.
- `aria_nbv/.venv/bin/pytest -q aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py --junitxml=/tmp/aria-nbv-panel-20260820-qa.xml` — 53 passed.
- Ruff format/check, changed-module `compileall`, and `git diff --check` passed.

## Canonical Owner Impact
Python reporting and Streamlit presentation owners plus their focused tests changed. No thesis, generation, schema, training, configuration, or guidance owner changed.
