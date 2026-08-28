---
id: 2026-08-28_target_orbit_candidate_mvp
date: 2026-08-28
title: "Target orbit candidate MVP"
status: done
topics: [candidate-generation, target-orbit, cuda, realism]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/pose_generation/types.py
  - aria_nbv/aria_nbv/pose_generation/candidate_generation.py
  - aria_nbv/aria_nbv/pose_generation/positional_sampling.py
  - aria_nbv/aria_nbv/pose_generation/candidate_mixture.py
  - aria_nbv/tests/pose_generation/test_candidate_mixture.py
  - docs/contents/evidence/candidate_target_orbit_mvp/README.md
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: 8fafa02fdb3441c9f9823f620728f413c6ecca91
repo_branch: "codex/candidate-target-orbit-mvp"
worktree_kind: linked
---

## Task

Resolve the one-sided target-relative proposal blocker with a small, testable
candidate family and real-data evidence without changing the production
mixture or seminar view-jitter invariant.

## Method

Mapped the candidate-generation owners, froze a two-scene equal-budget CUDA
evaluator, added a deterministic current-standoff partial-orbit family, and
iterated on independent code and architecture review findings. The final
candidate was replayed after the frame-semantics fixes and published with a
target-normalized support plot.

## Findings

- `positional_sampling.py` now constructs opt-in bilateral partial arcs in the
  world-horizontal plane and returns physical-reference offsets for motion
  checks.
- `candidate_generation.py` validates the orbit angle support and rejects
  one-row direct configurations; `candidate_mixture.py` appends stable position
  ID 6 and enforces actor-visible target context.
- The exact CUDA replay improved mean best target-root gain from `0.046999` to
  `0.048152`, target lateral balance from `0.000` to `0.208`, and worst-state
  valid support from `21` to `26` across two real scenes.
- One family/state pair still has zero valid rows. Family-aware refill and
  scale-up admission therefore remain unresolved rather than being hidden by
  aggregate validity.

## Commits

- [8fafa02fdb3441c9f9823f620728f413c6ecca91](https://github.com/JanDuchscherer104/ARIA-NBV/commit/8fafa02fdb3441c9f9823f620728f413c6ecca91) — implementation, regressions, and evidence bundle

## Verification

- `pytest aria_nbv/tests/pose_generation -q`: `56 passed, 1 skipped`.
- `ruff check` and `ruff format --check` over pose generation: pass.
- Exact post-review CUDA replay: all frozen hard gates pass; nonzero and bounded
  view jitter both remain `1.0`.
- Independent `code-reviewer` and `architect` passes: approved with zero final
  findings after world-frame, physical-offset, and bilateral-count repairs.

## Canonical Owner Impact

The pose-generation enum, configuration, sampler geometry, provenance mapping,
and regression tests are updated in their exact Python owners. The production
mixture/configuration is intentionally unchanged. The evidence bundle is a
non-canonical pilot snapshot and explicitly does not admit scale-up.
