---
id: 2026-08-25_exact_root_scene_carrier_extraction
date: 2026-08-25
title: "Exact root scene carrier extraction"
status: done
topics: [qh, scorer, scene, refactor, autoresearch]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
touched_owner_paths:
  - aria_nbv/aria_nbv/vin/modules/qh_scene_encoders.py
  - aria_nbv/aria_nbv/vin/modules/__init__.py
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/tests/vin/test_qh_scene_encoders.py
  - aria_nbv/tests/vin/test_target_finite_horizon.py
  - Makefile
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: b6d2ff31b21a88ce184a1719b29dc1b5e508b6a9
repo_branch: "codex/scorer-scene-encoder-seam"
worktree_kind: linked
---

## Task

Extract the exact `root_moments_v1` scene construction behind one modular
finite-horizon scene-carrier boundary without changing executable semantics or
serialized identity.

## Method

Graphify routed scene-representation ownership before exact Python and active
thesis sources were opened. A theory-rich professor review separated the
behavior-preserving carrier seam from the later privileged CF+ S1 experiment.
The inline root-EVL and semidense-point moment construction moved into one
parameter-free module; the learned scorer-owned projection did not move.

A two-process harness instantiated the parent and child source trees with the
same seeds and actor fixture, then compared configuration, learned state,
regression outputs, feasibility outputs, CORAL values, and CORAL logits by
content digest. A second professor review audited the repaired diff.

## Findings

- `qh_scene_encoders.py` owns the exact actor-to-root-summary operation and
  states which scorer inputs it cannot read.
- The output remains `[B,F_scene]`; a dynamic state axis is not introduced by
  this refactor.
- The inherited point-support scalar divides by batch-padded point-axis width,
  so it is batch-composition dependent and is not a per-chain density estimate.
  That limitation is now explicit and regression-tested without changing the
  value.
- `scene_projection` remains scorer-owned. Configuration hash, 44 learned-state
  keys, all tensor values, regression predictions, feasibility predictions,
  CORAL decoded values, and CORAL logits match the parent exactly.
- The next valid S1 comparison holds the privileged CF+ population fixed: H0
  receives but ignores selected depth, while S1 consumes the same causal
  prefix. CF0/H0 versus CF+/S1 is rejected as a source/representation confound.

## Commits

- [b6d2ff31b21a88ce184a1719b29dc1b5e508b6a9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b6d2ff31b21a88ce184a1719b29dc1b5e508b6a9) — exact parameter-free root scene carrier seam

## Verification

- Focused Ruff and 39 scene/scorer tests: pass.
- `make qh-ci ... PYTEST_WORKERS=auto`: formatting and lint pass; 557 tests pass.
- Parent/child config hash: `12e4990ecd334017` in both.
- Parent/child learned-state digest:
  `4b990facc68d03ce1c548a49f2f58a6004ee1a54345b347a0ceb7f91b18ffd11`
  in both; regression and CORAL output digests also match exactly.
- Professor-critic final review: approve, no P0-P2 findings.
- Graphify was used for navigation independently of the stale seeded projection;
  consequential claims were verified from exact sources and tests.

## Canonical Owner Impact

Python owns the extracted scene-carrier construction and scorer wiring. Tests
own numerical, mask-adjacent, padding-support, config, state, regression, and
CORAL compatibility. Active Typst remains unchanged because this iteration
does not alter the already documented `root_moments_v1` semantics. The
autoresearch report and this debrief are evidence only.
