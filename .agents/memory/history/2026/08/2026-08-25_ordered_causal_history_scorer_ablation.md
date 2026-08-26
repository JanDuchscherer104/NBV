---
id: 2026-08-25_ordered_causal_history_scorer_ablation
date: 2026-08-25
title: "Ordered causal history scorer ablation"
status: done
topics: [qh, scorer, history, transformer, thesis, autoresearch]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - docs/typst/thesis/sections/04-method
  - docs/typst/shared
touched_owner_paths:
  - aria_nbv/aria_nbv/vin/encoders/fourier.py
  - aria_nbv/aria_nbv/vin/encoders/pose.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/vin/modules/qh_history_encoders.py
  - aria_nbv/tests/lightning/test_qh_experiment.py
  - aria_nbv/tests/vin/test_learnable_fourier_features.py
  - aria_nbv/tests/vin/test_qh_history_encoders.py
  - aria_nbv/tests/vin/test_target_finite_horizon.py
  - docs/typst/shared
  - docs/typst/thesis/sections/04-method
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 41d41929fbf50f28098582904cf755b130dc7b7f
repo_branch: "codex/scorer-ordered-history"
worktree_kind: linked
---

## Task

Implement and measure a modular ordered causal pose-history carrier without
changing the accepted conditional-Q, hard-mask, scalar-horizon, candidate
equivariance, or compact scene-carrier contracts.

## Method

Graphify routed the owner traversal, after which exact Python, tests, and active
Typst owners defined the change. H0 preserves the original parameter-free
masked mean. H1 expresses every selected pose in the current camera frame,
adds normalized relative age, applies causal self-attention, and reads the last
valid token. A professor-critic reviewed the design before implementation and
re-reviewed the exact head before measurement.

The measurement held A1 state fusion, direct regression, dataset, optimizer,
one-epoch compute, seeds, and exact-Q2 audit fixed across five paired H0/H1 GPU
runs. Verified bundles were benchmarked on one real `[1,8,60]` CUDA batch.

## Findings

- `qh_history_encoders.py` now owns a deep H0/H1 state-carrier boundary. H1 is
  causal, padding-safe, order-sensitive, and candidate-independent.
- `target_finite_horizon.py` consumes exactly one history token and keeps H0 as
  the checkpoint-compatible default. H1 identity is nested in scorer and
  inference-bundle manifests.
- LFF and pose configurations expose complete emitted widths, including an
  optional raw-input residual, so attention compatibility fails before module
  construction.
- Active method equations, notation, glossary, and prose define the exact H0/H1
  semantics and label H1 exploratory.
- Across five matched seeds, H1-minus-H0 validation loss was -0.0001165 with a
  95% interval of [-0.0035100, 0.0032770], while exact-Q2 MAE was -0.0297108
  with [-0.1228415, 0.0634198]. Neither supports promotion. H1 added 14.3%
  parameters and 0.6439 ms mean latency, with a positive 95% interval.
- Every bundle had only four factual exact-Q2 rows and failed the longer-horizon
  gate. H0 therefore remains default; H1 is retained as a named ablation.

## Commits

- [7d8c948740](https://github.com/JanDuchscherer104/ARIA-NBV/commit/7d8c948740) — modular H0/H1 history carrier
- [8191561708](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8191561708) — ordered-history invariants
- [27a05f35d8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/27a05f35d8) — active thesis and shared notation
- [41d41929fb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/41d41929fb) — emitted-width and H1 bundle hardening

## Verification

- Focused Ruff plus 63 tests: pass.
- `make qh-ci ... PYTEST_WORKERS=0`: Ruff pass; 552 tests pass.
- Typst authoring, marker, glossary generation, and thesis compile gates: pass.
- Ten exact-head one-epoch RTX 3080 Ti fits: pass, two optimizer updates each.
- Ten bounded exact-Q2 audits: executed; all scientific promotion gates remain
  closed because support is insufficient and learned recursion does not pass.
- Professor-critic exact-head review: no P0-P2 implementation or ownership
  findings; measurement and publication approved.

## Canonical Owner Impact

Python owns executable H0/H1 construction, shape, causality, and manifest
identity. Tests own public invariants and bundle compatibility. Active Typst
method sections plus shared symbols/equations/glossary own the scientific
meaning and non-promotion boundary. Autoresearch reports and this debrief are
evidence only, not competing truth owners.
