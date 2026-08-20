---
id: 2026-08-20_training_data_page_ownership_cleanup
date: 2026-08-20
title: "Training Data Page Ownership Cleanup"
status: done
topics: [streamlit, training-data, q-h, rollout-inspection, simplification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/app/panels/offline_dataset.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
---

## Task

Reduce default clutter and duplicate summaries across Training Dataset, Root
Observation Store, and Rollout Supervision without changing presentation-free
read models or removing advanced inspection capabilities.

## Result

Training Dataset now leads with Q_H admission facts established by the real
preflight; root, rollout, and target diagnostics remain in their dedicated
tables or explicit Details scan. Root Observation Store groups its eleven peer
tabs into Overview, Content, Runtime, and Details while retaining every prior
diagnostic renderer. Rollout Supervision keeps aggregate Q_H facts in Overview
and moves store-qualified inclusion and Q_H evidence to Drill-down.

The three page modules are 73 lines smaller in aggregate. Q_H construction,
deep target scans, corpus aggregation, store validation, export, selected-depth
inspection, and Rerun remain explicit and lazy.

## Verification

The focused dataset-bundle, reporting, router, Streamlit panel, and offline
inventory suite passed 79 tests. Ruff format/check, module compilation, focused
progressive-disclosure tests, and `git diff --check` passed in the shared ARIA
environment. Graphify was unusable because its projection revision and owner
digests were stale, so exact source and tests remained authoritative.
