---
id: 2026-09-01_streamlit_candidate_snapshot_retention_architecture_pr4b
date: 2026-09-01
title: "Streamlit Candidate Snapshot Retention Architecture PR4b"
status: done
topics: [streamlit, candidate-generation, rollout-inspection, architecture]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/app/candidate_evidence.py
  - aria_nbv/aria_nbv/app/controller.py
  - aria_nbv/aria_nbv/app/state_types.py
  - aria_nbv/aria_nbv/app/panels/candidate_evidence.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts/validity_support.py
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: efbca2fb83edc9b5fcf47a97958dd4e6f97277be
repo_branch: "codex/streamlit-candidate-snapshot-pr4b"
worktree_kind: linked
---

## Task
Make candidate inspection retain immutable snapshots and plot models once at
the application acquisition boundary instead of rereading stores or reducing
scientific facts during each Streamlit rerun.

## Method
Added a Streamlit-free retained view, a live-controller seam that accepts only
truthful canonical `CandidateSet` outputs, and one explicit stored-session
acquisition over typed rollout/step/target rows. Replaced render-time benchmark
support reduction with dynamic Streamlit 1.57 tabs that deserialize only the
visible retained plot model. Preserved replacement-sensitive store validation
and left legacy direct generation unchanged until its composition owner lands.

## Findings
- `aria_nbv/aria_nbv/app/candidate_evidence.py` owns the immutable app view and
  rejects empty, incomplete, or source-unbound snapshot/model products.
- `aria_nbv/aria_nbv/app/panels/_stored_rollouts/session.py` is the sole stored
  acquisition owner. It resolves one factual shell and validates the selected
  store identity before and after snapshot/model construction.
- `aria_nbv/aria_nbv/app/panels/candidate_evidence.py` is a render-only leaf: it
  imports no generator, store reader, benchmark reducer, or plot builder.
- Direct legacy `CandidateSamplingResult` inspection cannot truthfully produce
  canonical evidence because the current page lacks actor/source/mesh/program
  bindings. G031 owns that migration after rollout composition propagates them;
  this workpackage adds no reverse or fabricated adapter.

## Commits
- [efbca2fb83edc9b5fcf47a97958dd4e6f97277be](https://github.com/JanDuchscherer104/ARIA-NBV/commit/efbca2fb83edc9b5fcf47a97958dd4e6f97277be) — retain canonical candidate evidence and render only retained models.

## Verification
- App router, Streamlit entry, candidate snapshot, benchmark, stored laziness,
  and new retention suites: 94 passed.
- New retention contract: 8 passed, including a real persisted store, same-hash
  distinct live outputs, replacement invalidation, AppTest laziness, and exact
  live/stored plot-model equality.
- Ruff over every changed Python source and test: passed.
- Package-config mypy over the new view/renderer and stored session/panel
  owners: passed. Five existing controller/state-type errors at unchanged lines
  remain outside this diff.
- Independent exact-diff architecture/Python/Streamlit review: no actionable
  P0-P2 findings.

## Canonical Owner Impact
Application state, controller, stored-session, and candidate-panel Python owners
plus their AppTest contracts were updated. No candidate algorithm, rollout
persistence schema, configuration, Streamlit cache plane, or thesis claim
changed.
