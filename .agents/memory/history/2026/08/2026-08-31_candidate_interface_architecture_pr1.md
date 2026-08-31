---
id: 2026-08-31_candidate_interface_architecture_pr1
date: 2026-08-31
title: "Candidate interface architecture PR1"
status: done
topics: [candidate-generation, architecture, parity, cuda]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation
  - aria_nbv/aria_nbv/rollouts/replay/policy.py
  - aria_nbv/aria_nbv/utils/canonical_binding.py
  - aria_nbv/tests/pose_generation/test_candidate_interface.py
  - aria_nbv/tests/integration/test_candidate_interface_rollout_store.py
  - scripts/benchmark_candidate_interface_pr1.py
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: 0ff06c738c132998b1dd8e50b3c15879243013bf
repo_branch: "codex/candidate-interface-pr1"
worktree_kind: linked
---

## Task
Land Architecture PR 1 of the candidate/rollout modularization program as a
parity-only, final public candidate-generation boundary.

## Method
Introduced literal program, bound request/scene/actor, attempted-table,
admission, completion, and candidate-set contracts; assembled the canonical
set directly; retained a one-way fixed-valid legacy projection; and compared
the new path with the shipped path through focused, store, and real-scene CUDA
characterization.

## Findings
- `aria_nbv/aria_nbv/pose_generation/candidate_program.py` owns the bounded,
  closed center/gaze program and randomness/completion constraints.
- `aria_nbv/aria_nbv/pose_generation/candidate_interface.py` owns explicit
  value bindings, mutation receipts, typed candidate/admission evidence, and
  the one-way `A = V` compatibility projection.
- `aria_nbv/aria_nbv/pose_generation/program_generator.py` produces the
  canonical `CandidateSet` directly while reusing one prepared geometry query.
- Exact legacy shell, view, mask, rule, seed, lineage, selection, invalid-reason,
  and Zarr store parity was retained. The nonzero seminar-jitter contract and
  per-row boundedness/limits remain unchanged.
- Production replay remains intentionally on the legacy facade until
  Architecture PR 6. Replay does not yet possess truthful actor/source/mesh
  identities; `RolloutDatasetWriter._rollout_target` is the future composition
  owner. No placeholder identity was introduced.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/0ff06c738c132998b1dd8e50b3c15879243013bf

## Verification
- Focused candidate interface plus rollout/store integration: 38 passed.
- Pose generation plus replay/store: 167 passed, 1 skipped.
- Rollout, oracle, VIN, and campaign matrix: 410 passed.
- Package-config mypy for all six new source modules: passed.
- Targeted Ruff format/lint and replay/oracle CPU golden: passed.
- CUDA benchmark on an RTX 3080 Ti, CUDA 12.1, Torch 2.4.1, scenes 81283
  and 81807: exact shell/view/mask equality; five 30-call warm batches and five
  cold starts; all latency, memory, transfer, prepared-query, and center-call
  gates passed.
- Root `make replay-oracle-golden` could not resolve the linked worktree's
  absent `external/efm3d` package metadata; the identical script passed through
  the repository shared environment with an absolute worktree `PYTHONPATH`.

## Canonical Owner Impact
Current truth is updated in the Python/test/script owners listed in
`touched_owner_paths`. No further canonical updates are required for PR 1;
the production replay composition migration remains owned by Architecture PR 6.
