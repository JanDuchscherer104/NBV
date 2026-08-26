---
id: 2026-08-24_state_keyed_proposal_streams_and_sequence_visualization
date: 2026-08-24
title: "State keyed proposal streams and sequence visualization"
status: done
topics: [candidate-generation, replay, rng-lineage, streamlit]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/replay/policy.py
  - aria_nbv/aria_nbv/rollouts/replay/engine.py
  - aria_nbv/aria_nbv/rollouts/replay/state.py
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - aria_nbv/aria_nbv/app/panels/candidates.py
  - aria_nbv/tests/fixtures/replay_oracle_golden.json
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: 9d7ec4fb4f3bb46f28809d78f162000d780083c9
repo_branch: "codex/candidate-mvp-02-state-streams"
worktree_kind: linked
---

## Task
Decouple proposal and selection randomness, make candidate shells invariant to frontier ordering, and visualize within-shell sampling order.

## Method
Keyed proposal seeds by campaign proposal root, selected full-shell history, and explicit replica. Keyed selection separately by recipe seed and the same state history. Added row-aligned proposal provenance and a reference-ground-plane Plotly view coloured by draw order.

## Findings
The replay engine previously derived both streams from a recipe seed and transient frontier indices, so beam reordering could change candidate support. Campaign planning now supplies a temperature-independent proposal root, while step tables continue to retain exact candidate and selection seeds. The Candidates page exposes sequence clumping and validity without treating action selection as proposal generation. Because the deterministic replay contract intentionally changed its candidate poses and separately keyed random selections, the checked-in replay/oracle golden was regenerated from the canonical verifier.

## Commits
- [9d7ec4fb4f3bb46f28809d78f162000d780083c9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9d7ec4fb4f3bb46f28809d78f162000d780083c9)
- [9632e46899dafc71b093c5c73ba8c6f5d3761491](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9632e46899dafc71b093c5c73ba8c6f5d3761491)

## Verification
- Ruff passed for changed Python owners and tests.
- 46 focused replay, plotting, and Candidates-panel tests passed.
- Three clean-worktree campaign planning/adaptation tests passed, including four-temperature proposal-root sharing.
- Thesis compilation and `make typst-authoring-contract` passed.
- Replay/oracle golden parity passed on a second deterministic generation, and 54 focused replay, mixture, plotting, and golden-contract tests passed.

## Canonical Owner Impact
Updated replay seed derivation and state identity, campaign seed lineage/adaptation, candidate provenance visualization, focused tests, and the active thesis method contract. No further canonical updates are pending for this slice.
