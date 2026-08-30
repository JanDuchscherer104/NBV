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
repo_head: 9da250a3492119b2aaf515152d9efc5be4a61ad6
repo_branch: "codex/candidate-family-preflight"
worktree_kind: linked
---

# WP02 candidate-family preflight and Phase-A gate

## Task and method

WP02 froze one presentation-free candidate-family reducer for rollout-store
preflight, campaign admission, plotting, and Streamlit. It separates the
resolved root floor from the versioned family floor and treats no-label Phase A
as incapable of establishing flat target-root gain. The existing campaign
preflight command was extended to generate candidate shells directly from the
reviewed 100-scene source manifest without constructing a scorer, renderer,
replay policy, or oracle reward label.

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

The canonical JSON has artifact SHA-256
`78632654ffb1bdf8cc085874483547f090bb6013eab5264efe35a5628c39d356`
and file SHA-256
`6041f70a031c64c9140de13e11f403b54c614785492315e403a7c57d465a64f1`.
It records execution revision
`31888f86fc6348ef223e5c606f7ad41fda7e3082`, source-manifest file SHA-256
`d6e771d1582394cde9005be3185dc9cfbb875cab5fc004f184922a25dc996f56`,
and native source-store manifest identity `605453ba11869e40`.

## Issue #54 acceptance

- Threshold formula, persistence, state/family applicability matrix, typed
  family failures, no-label flat-gain semantics, and focused tests are
  evidenced.
- The required all-100-scene Phase-A run is evidenced and fails closed with an
  exact blocker taxonomy.
- The sampler-pass criterion is not met. Issue #54 remains open until a
  remediated configuration passes the same frozen gate; forward support cannot
  fill target-family deficits.

## Verification

- Exact family/info/plot/panel/cache/source-adapter suite: 81 passed.
- Campaign regression suite: 189 passed.
- Execution-identity and no-go exit regressions: 4 passed.
- Strict focused mypy: seven changed Python owners passed.
- Ruff check/format, Agents-DB validation, agent-memory validation, thesis
  compilation, and `git diff --check` passed.
- Exact 100-scene command exited 2 after atomically writing the complete no-go
  artifact. The full heatmap and funnel views were reconstructed through the
  canonical reducer and plotting helper; their SVG SHA-256 values are
  `42e089c1c3e2bc2ff741761d79df4126c4bcb5303a77f3925774b1159200f7f4`
  and `6bc24e385d326481147c265b07bd7685ef3154d20343881c24e103e810b34077`.
  The legible one-scene-per-stratum thesis projection has SVG SHA-256
  `0a185abcb917e571393fee7154587a6245af301993e3b59b202cc496cc32f478`.

## Canonical impact

The preflight interface, typed blocker taxonomy, Phase-A adapter, and thin UI
consumer are current implementation owners. The empirical artifact records a
failed unchanged control and must not be cited as a passing support gate, an
RRI result, or permission for broad generation.

## Commits

- [Core family-preflight contract](https://github.com/JanDuchscherer104/ARIA-NBV/commit/41622351da702465de66e12a151fa690a1d564fb)
- [Campaign Phase-A execution identity](https://github.com/JanDuchscherer104/ARIA-NBV/commit/31888f86fc6348ef223e5c606f7ad41fda7e3082)
- [100-state plotting repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/9da250a3492119b2aaf515152d9efc5be4a61ad6)
