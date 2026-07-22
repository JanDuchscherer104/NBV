---
id: 2026-07-21_streamlit_training_dataset_hub
date: 2026-07-21
title: "Streamlit Training Dataset Hub and Navigation Cleanup"
status: done
topics: [streamlit, vin-offline-store, rollouts, dataset-inspection, navigation]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/streamlit_app.py
  - aria_nbv/aria_nbv/app/app.py
  - aria_nbv/aria_nbv/app/__init__.py
  - aria_nbv/aria_nbv/app/panels/__init__.py
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/dataset_bundle.py
  - aria_nbv/tests/test_streamlit_entry.py
  - aria_nbv/tests/test_dataset_bundle.py
  - aria_nbv/tests/app/test_app_router.py
  - aria_nbv/tests/app/panels/test_training_dataset_panel.py
---

## Task

Remove Streamlit cache warnings emitted before a runtime exists, reorganize the
application around grouped page-owned navigation, and add a Training Dataset
hub for inspecting one immutable VIN root store together with multiple rollout
supervision stores.

## Method and outputs

- Made the Streamlit entry point and panel facade import-light, with lazy page
  imports so cached functions are not registered before Streamlit creates its
  runtime.
- Replaced the global single-step pipeline sidebar with page-owned controls and
  grouped navigation for Training Data, Generation, Models & Experiments, and
  historical Foundations / Single-step pages.
- Added a read-only bundle projection over one explicit VIN root and multiple
  rollout stores. Compatibility uses the canonical VIN manifest plus
  per-source identity evidence; incompatible or blocked stores remain visible
  but are excluded from aggregate totals.
- Kept root-store blockers scoped to the root itself: dependent rollout or
  topology findings remain visible without making an otherwise usable root
  appear blocked.
- Added immediate lightweight summaries and explicit validation/deep-statistics
  actions. The hub keeps root GT-OBB opportunities, persisted rollout targets,
  unique target tasks, and candidate-level trainable rows as separate
  denominators. Lightweight identity checks read bounded metadata only; failed
  deep projections report unavailable or partial evidence rather than false
  zero counts.
- Added split/store topology, CORAL artifact provenance, findings, and a
  deterministic JSON evidence download without changing VIN or rollout schemas.

## Verification

- Targeted Streamlit, topology, bundle, dispatcher, VIN-store, rollout
  inspection, and app tests passed after final cleanup (`169 passed`).
- Ruff formatting checks and lint passed for the task-owned Python files.
- A final headless Streamlit health smoke on port `8522` returned `ok`; startup
  contained zero `No runtime found, using MemoryCacheStorageManager` warnings.
- Task-scoped diff checks passed. Repository-wide diff checking still reports
  unrelated pre-existing Typst conflict markers, which were not modified or
  absorbed into this task.
- The Graphify code graph was refreshed. Its freshness checker remains stale
  because the repository corpus is dirty and documentation extraction is still
  pending.
- `make check-agent-memory` remains blocked by the same two unrelated existing
  `.omx/plans` files that lack YAML frontmatter.

## Canonical state impact

No persisted VIN/rollout schema, rollout generation policy, training contract,
or source dataset was changed. Dataset selection remains session-local and the
new hub is a read-only inspection surface, so no canonical state update is
required.
