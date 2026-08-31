---
id: 2026-08-30_candidate_family_preflight_wp02
date: 2026-08-30
title: "WP02 Candidate-Family Preflight and Phase-A Gate"
status: done
topics: [candidate-generation, rollouts, preflight, phase-a, evidence]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/candidate_benchmark.py
  - aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py
  - aria_nbv/aria_nbv/rollouts/info_cli.py
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/pipelines/cli.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts
  - docs/typst/thesis/sections/04-method/04-03-candidate-and-replay-contract.typ
  - docs/contents/evidence/candidate_family_phase_a_wp02.json
codex_thread: codex://threads/01a05281-f9f7-7f80-967e-4000d77aca81
repo_object_format: sha1
repo_head: 2baf7cf6b276b81c50d01d45b152016d7cf68033
repo_branch: "codex/candidate-family-preflight"
worktree_kind: linked
---

# WP02 candidate-family preflight and Phase-A gate

## Task and method

WP02 froze one presentation-free candidate-family reducer for rollout-store
preflight, campaign admission, plotting, and Streamlit. It separates the
resolved root floor from the versioned family floor and treats Phase A as
incapable of establishing flat target-root gain without reward labels. The
existing campaign preflight command was extended to generate candidate shells
directly from the reviewed 100-scene source manifest without constructing a
scorer, renderer, replay policy, or reward label. This is a no-render,
no-reward-label proposal-support audit with privileged GT target instruction
and mesh validity, not an oracle-free path.

## Findings

The exact-head run used the reviewed source store
`vin_offline_rollout_campaign100_v10_rebuilt` and covered 100 source rows, 100
scenes, and 100 target states without exclusions. It attempted 6,000 candidates
and admitted 3,146 rows to compact valid shells. The result is a no-go with 76
typed blockers: 44 applicable-family collapses, 24 low non-forward
target-family-support failures, and 8 low-root-support failures. `flat_gain` is
unavailable with denominator zero. Broad rollout generation remains blocked
both by this failed gate and by the independent WP18 requirement; issue #54
must remain open.

The compact canonical JSON has artifact SHA-256
`26d4ddefb007151d9975024478889fb0b3c30f82949429501d39d2d91a7acc23`
and file SHA-256
`f4c9d8399f7f898495a02e43795f402f734ee9aa3975632762c8d606b0a204ab`.
It records execution revision
`2baf7cf6b276b81c50d01d45b152016d7cf68033`, generation revision
`a2ae86b7463930c9`, source-manifest file SHA-256
`d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56`,
native source-store manifest identity `605453ba11869e40`, writer configuration
SHA-256 `fc47d06e76da64a51948429a60a59efcb685962e9f475f0b80865031b127f91b`,
and the Python 3.11.15, PyTorch 2.4.1/CUDA 12.1, PyTorch3D 0.7.9,
RTX 3080 Ti runtime identity.

## Issue #54 acceptance

- Threshold formula, persistence, state/family applicability matrix, typed
  family failures, state-conditional no-reward-label flat-gain semantics, and focused tests are
  evidenced.
- The required all-100-scene Phase-A run is evidenced and fails closed with an
  exact blocker taxonomy.
- The sampler-pass criterion is not met. Issue #54 remains open until a
  remediated configuration passes the same frozen gate; forward support cannot
  fill target-family deficits.

## Verification

- Broad campaign/family/info/panel/cache/source-adapter suite: 277 passed.
- Execution-identity and no-go exit regressions: 4 passed.
- Strict focused mypy: seven changed Python owners passed.
- Ruff check/format, Agents-DB validation, agent-memory validation, thesis
  compilation, and `git diff --check` passed.
- Exact 100-scene command exited 2 after atomically writing the complete no-go
  artifact. The full heatmap and audit-stratum funnel views were reconstructed
  through the dedicated reader and plotting helper; their SVG SHA-256 values are
  `78e7928f5a65f62c6fe08870d109c5dc36e97bfb22ff87287311fc2cc5b98957`
  and `ca17e5ca33bb404f7532122c3aa6bc0601c88b3b21e07a586f0fdb8610749144`.
  The legible one-scene-per-stratum thesis projection has SVG SHA-256
  `9fa6e3c2881366f42eac9071617bab79eb931f472ef4d1724a4b03688f4b0ae7`.

## Canonical impact

The preflight interface, typed blocker taxonomy, Phase-A adapter, and thin UI
consumer are current implementation owners. The empirical artifact records a
failed unchanged control and must not be cited as a passing support gate, an
RRI result, or permission for broad generation.

## Commits

- [Fail-closed family admission repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/cf9e44d468fb9688872f772544b7bd4aeb7d8fdb)
- [Frozen campaign execution head](https://github.com/JanDuchscherer104/ARIA-NBV/commit/2baf7cf6b276b81c50d01d45b152016d7cf68033)
- [Canonical reader order repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/801dbae07f)
