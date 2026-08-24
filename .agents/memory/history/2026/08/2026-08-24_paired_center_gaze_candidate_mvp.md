---
id: 2026-08-24_paired_center_gaze_candidate_mvp
date: 2026-08-24
title: "Paired center gaze candidate MVP"
status: done
topics: [candidate-generation, paired-intervention, streamlit, thesis]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/candidate_generation.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/aria_nbv/pose_generation/plotting.py
  - aria_nbv/aria_nbv/app/panels/candidates.py
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: 5a1d3a9c016219792503e337bf83a6984bf51167
repo_branch: "codex/candidate-mvp-03-paired-gaze"
worktree_kind: linked
---

## Task
Add a minimal controlled candidate rule that evaluates different gaze families at identical camera centers and visualizes the intervention.

## Method
Added an explicit-centre generation seam that rebuilds orientations and reapplies hard rules, then extended mixture components with one optional paired view mode. Added stable pair/variant row provenance, a 60-row paired preset, and a ground-plane ray visualization.

## Findings
`candidate_generation.py` can now orient and validate supplied world-space centers. `candidate_mixture.py` uses that seam to retain a source row and an alternative-gaze row with identical translation. Both remain independent actions with normalized proposal mass. The Candidates page renders shared centers, both gaze rays, components, variants, and validity.

## Commits
- [5a1d3a9c016219792503e337bf83a6984bf51167](https://github.com/JanDuchscherer104/ARIA-NBV/commit/5a1d3a9c016219792503e337bf83a6984bf51167)

## Verification
- Ruff passed for changed Python owners and tests.
- 124 pose-generation, replay, Candidates-page, and counterfactual-panel tests passed.
- Thesis compilation and `make typst-authoring-contract` passed.

## Canonical Owner Impact
Updated candidate generation/mixture owners, row provenance, visualization, focused tests, and the active thesis method contract. No production rollout profile adopts the paired preset yet; it remains an explicit MVP/ablation option pending benchmark evidence.
