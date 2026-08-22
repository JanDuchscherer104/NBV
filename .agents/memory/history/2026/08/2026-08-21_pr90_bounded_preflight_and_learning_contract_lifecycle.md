---
id: 2026-08-21_pr90_bounded_preflight_and_learning_contract_lifecycle
date: 2026-08-21
title: "PR90 bounded preflight and learning contract lifecycle"
status: done
topics: [qh, rollouts, lightning, contracts, pr90]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/01a02339-86df-7f13-a17b-fbd6626ab8c4
---

## Task
Implement the bounded selected-depth preflight and exact Q_H learning-contract lifecycle plan for PR #90.

## Method
Verified the reviewed baseline and canonical owners, then applied four ordered work packages: bounded profile-aware Zarr validation, learning-contract checkpoint binding, shared Lightning lifecycle admission, and contract-documentation repair. Each work package was committed independently and checked before the next one.

## Findings
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` and `qh_reader.py` now avoid selected-depth payload reads for CF0 and validate CF+ payloads in finite persisted chunks without weakening structural checks.
- `aria_nbv/aria_nbv/lightning/qh_datamodule.py` exposes a deterministic hash of the complete effective `QhDataContract`; `qh_module.py` requires and checks it before fit, validate, test, and predict lifecycles.
- Named `qh_cf0_v1` data now requires `v1_observed`; legacy unnamed V0 diagnostic construction remains available, and CF+ privilege is explicit.
- Current schema and candidate-camera transform documentation now match executable owners.

## Verification
- Focused combined matrix: 213 passed.
- `make qh-ci QH_CI_PYTHON=.venv/bin/python PYTEST_WORKERS=0`: 389 passed; Ruff clean.
- `make ruff-full package-smoke PYTEST_WORKERS=0 QH_CI_PYTHON=.venv/bin/python`: Ruff and targeted mypy clean; Q_H suite 389 passed; package smoke 123 passed.
- `git diff --check` passed, and the package import resolved to this worktree.

## Canonical Owner Impact
The rollout validator/reader, Q_H dataset/profile views, DataModule, Lightning module, their focused tests, and current data-handling/Zarr documentation were updated. No schema, dependency, scorer, service, campaign-generation, or public batch-shape owner changed.
