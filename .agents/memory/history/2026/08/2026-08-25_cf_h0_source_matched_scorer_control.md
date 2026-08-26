---
id: 2026-08-25_cf_h0_source_matched_scorer_control
date: 2026-08-25
title: "CF+ H0 source-matched scorer control"
status: done
topics: [qh, vin, scorer, counterfactual-depth, autoresearch]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/data_handling/qh_contracts.py
  - aria_nbv/aria_nbv/data_handling/qh_data/views.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/lightning/qh_module.py
  - aria_nbv/aria_nbv/lightning/qh_experiment.py
  - docs/typst/shared/equations/model.typ
  - docs/typst/shared/glossary.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 12f9e1976a616318ac9ec7c0fccd161955642dd4
repo_branch: "codex/scorer-cfplus-h0-control"
worktree_kind: linked
---

## Task
Create a source-matched CF+ null scorer that validates the exact causal selected-depth
carrier but cannot consume its numeric payload, preserving a clean H0 control for the
first S1 scene-memory comparison.

## Method
Moved named profile and carrier validation into a dependency-light QH contract owner,
admitted `qh_cfplus_gt_depth_v1` only as a privileged training profile, and tested
payload invariance, causal support, profile alignment, and fail-closed bundle behavior.
The active thesis equation and glossary were updated in the same atomic workpackage.

## Findings
`target_finite_horizon.py` can now execute CF+ H0 without treating depth availability as
scene evidence. `qh_contracts.py` validates source, tensor, device, padding, and exact
`j < s` prefix support at data and scorer boundaries. `qh_experiment.py` still rejects
CF+ from deployable bundles even if privilege or target-protocol metadata is rehashed.
Direct RTX 3080 Ti one-update fits succeeded for both regression and CORAL decoders,
but the available CF+ stores have no held-out test split; these are trainability smokes,
not generalization evidence.

## Commits
- `12f9e1976a616318ac9ec7c0fccd161955642dd4` — CF+ H0 implementation, tests, and
  thesis alignment.

## Verification
- `make qh-ci PYTEST_WORKERS=0`: 570 passed.
- `make thesis-pdf-ci`: passed.
- `make quarto-docs-ci`: passed with pre-existing unresolved-reference warnings.
- Professor-critic: APPROVE, no P0-P2 findings.
- Regression and CORAL direct Lightning GPU smokes: one optimizer update each and
  finite validation loss on the matched CF+ train/validation carrier.

## Canonical Owner Impact
Python now owns the executable CF+ H0 admission, carrier invariance, and deployment
boundary. Active Typst owns the same source-matched-control meaning. No canonical
owner update remains pending from this workpackage.
