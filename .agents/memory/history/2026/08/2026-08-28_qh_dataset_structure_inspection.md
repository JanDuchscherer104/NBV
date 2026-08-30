---
id: 2026-08-28_qh_dataset_structure_inspection
date: 2026-08-28
title: "QH Dataset Structure Inspection"
status: done
topics: [qh, streamlit, typing, diagnostics, simplification]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/dataset_bundle.py
  - aria_nbv/aria_nbv/utils/rich_summary.py
  - aria_nbv/aria_nbv/data_handling/qh_data/views.py
codex_thread: codex://threads/01a04851-6406-72a3-95cc-204f29b7389e
repo_object_format: sha1
repo_head: 1adcb67b4a177293fd9d9460df878e6083e41205
repo_branch: main
worktree_kind: primary
---

## Task

Replace the Q_H corpus tab's hand-selected tensor preview with a direct view of one typed `QhChain` dataset item and one typed `QhBatch` produced by the production `QhDataModule` loader.

## Method

Deleted the lossy `QhBatchPreview` DTO and manual tensor unpacking. The selection boundary now returns the domain objects directly, while `rich_summary` recursively traverses their dataclass composition and summarizes tensor wrappers without copying or moving them. Streamlit caches only the rendered strings and keeps finite floating-point statistics opt-in.

## Findings

The Q_H domain classes and data module already owned the complete item, collation, and typing contracts. The missing tensors were caused by a second, manually maintained preview schema in `dataset_bundle.py`, not by the dataset or collator.

## Verification

- Ruff passed for all touched Python and test files.
- Mypy passed for the dataset bundle, Q_H data module, Rich summary adapter, and Streamlit panel.
- 39 focused Rich-summary, Q_H bundle, and Streamlit panel tests passed.
- `git diff --check` passed.

## Canonical-State Impact

The exact Python owners and regression tests now encode the direct typed item-and-batch inspection contract. No additional canonical update is needed.

## Commits

none
