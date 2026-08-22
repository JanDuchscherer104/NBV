---
id: 2026-08-23_online_oracle_mvp_foundation
date: 2026-08-23
title: "Online Oracle MVP Foundation"
status: done
topics: [online-oracle, qh, vin, immutable-bundle, dense-valid]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/vin/qh_bundle.py
  - aria_nbv/aria_nbv/lightning/qh_experiment.py
  - aria_nbv/aria_nbv/lightning/qh_module.py
  - aria_nbv/aria_nbv/data_handling/qh_data/batching.py
  - aria_nbv/aria_nbv/lightning/qh_datamodule.py
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/aria_nbv/oracle/environment.py
  - aria_nbv/aria_nbv/oracle/pipelines/online_qh.py
codex_thread: codex://threads/01a02aed-3d7c-7c80-b107-5e4985e839f0
repo_object_format: sha1
repo_head: 0bd33038905c04bf3fe9707703d384e80e2b500e
repo_branch: "codex/online-oracle-mvp"
worktree_kind: linked
---

## Task
Implement the receipt-authorized, gate-safe foundation of the online-oracle MVP
plan and publish it for review without claiming downstream scientific gates.

## Method
Used the fresh Graphify graph to route exact owners, then implemented the
production scorer, dense-valid fitted-Q identity, immutable experiment bundle,
identity-bound decision context, inference Adapter, and deterministic CPU
golden fixture. Independent review focused on bundle integrity and online
context invariants before the affected-owner suite was run.

## Findings
The production `TargetFiniteHorizonScorer` is actor-only and differentiates its
parameters while keeping persisted EVL/semidense evidence detached. Q_H bundle
publication is immutable and validation-selected; loading verifies closed
contracts and all four required artifacts. Dense-valid query, support, and
objective identities now propagate through readers, collation, data admission,
and Zarr persistence. The online scoring seam binds candidate and actor payloads
to a frozen context and rejects stale or hard-invalid requests.

Complete WP0a, WP4, and the collection/retraining part of WP5 remain closed:
the checkout has no representative CUDA replay/oracle source bundle with the
required mesh, target, renderer, configuration, and source-manifest identity.
No hierarchical proposer or policy-improvement claim was introduced.

## Verification
`uv run ruff check` and `uv run ruff format --check` passed on all changed
Python owners and tests. Targeted mypy passed for the five new production
modules. `make qh-ci PYTEST_WORKERS=0` passed 393 tests, including distributed
smokes and API discovery. The deterministic golden contract passed through
`make replay-oracle-golden`.

## Canonical Owner Impact
Current truth changed in the Python owners listed by `touched_owner_paths`,
their focused tests, and the root `Makefile` golden-parity target. The plan and
implementation-status artifact retain the closed scientific promotion gates.
