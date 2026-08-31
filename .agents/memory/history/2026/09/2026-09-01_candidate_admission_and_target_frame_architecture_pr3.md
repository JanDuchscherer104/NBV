---
id: 2026-09-01_candidate_admission_and_target_frame_architecture_pr3
date: 2026-09-01
title: "Candidate admission and target-frame architecture PR3"
status: done
topics: [candidate-generation, admission, target-relative-frame, architecture, cuda]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/geometry/target_relative.py
  - aria_nbv/aria_nbv/pose_generation/admission.py
  - aria_nbv/aria_nbv/pose_generation/candidate_generation_rules.py
  - aria_nbv/aria_nbv/pose_generation/program_generator.py
  - aria_nbv/aria_nbv/rollouts/trace.py
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: c823e5675f94a573d618f6715d1e8d6478e3e3f6
repo_branch: "codex/candidate-admission-target-frame-pr3"
worktree_kind: linked
---

## Task
Land Architecture PR3 of the candidate/rollout modularization stack without changing shipped proposal values, ordering, seeds, seminar jitter, or legacy projection bytes.

## Method
Introduced one canonical target-relative frame and one immutable admission composer, migrated generation and rollout reducers to those owners, retained a cold diagnostic boundary for adversarial semantic validation, and characterized legacy parity through focused CPU/CUDA and storage tests.

## Findings
- `aria_nbv/aria_nbv/geometry/target_relative.py` now owns the right-handed target-forward/left/world-up frame, exact horizontal delta, invertible projections, typed degeneracy failures, and one-sync cold construction.
- `aria_nbv/aria_nbv/pose_generation/admission.py` now owns N-aligned criterion applicability, evaluation, pass/reason/source-role/margin facts and the cumulative-to-final validity chain. Production composition is structural and no-D2H; public cold diagnostics reject contradictory evidence.
- Candidate generation rules emit single-unit motion, support, endpoint-clearance, and path-clearance criteria. The legacy adapter recombines them without changing shipped masks or primary invalid reasons.
- Inspection, benchmark normalization, plotting coordinates, and persisted invalid-reason derivation now consume the canonical frame/admission owners rather than duplicate transforms or precedence logic.

## Commits
- [c823e5675f94a573d618f6715d1e8d6478e3e3f6](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c823e5675f94a573d618f6715d1e8d6478e3e3f6) — unify target-relative geometry and typed admission evidence.

## Verification
- Focused cross-contract suite: 377 passed, 1 skipped.
- Ruff targeted gate over all changed source/tests: passed.
- Public import typing contract: runtime import passed; independent strict mypy contract passed.
- Two real CUDA scenes (81283, 81807), RTX 3080 Ti, 5 cold calls and 5x30 warm calls: exact shell/view/mask parity, zero warm query acquisition, one center call per group, host-device transfers 108 calls/594 bytes versus legacy 122/746, all latency/RSS/CUDA gates passed.
- Independent exact-diff architecture review: no remaining P0-P2 findings.

## Canonical Owner Impact
Python geometry, candidate-generation, admission, rollout-reason, inspection, and benchmark owners were updated. No configuration, persistence schema, Typst, or setup contract changed.
