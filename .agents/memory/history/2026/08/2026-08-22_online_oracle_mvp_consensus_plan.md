---
id: 2026-08-22_online_oracle_mvp_consensus_plan
date: 2026-08-22
title: "Online Oracle MVP Consensus Plan"
status: done
topics: [qh, oracle, online-learning, evl, hierarchical-pose, ralplan]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .omx/context/online-oracle-mvp-20260822.md
  - .omx/plans/prd-online-oracle-mvp.md
  - .omx/plans/test-spec-online-oracle-mvp.md
  - .omx/plans/ralplan-handoff-online-oracle-mvp.md
  - .omx/specs/online-oracle-issue-acceptance.md
  - .agents/memory/history/2026/08/2026-08-22_online_oracle_mvp_consensus_plan.md
codex_thread: codex://threads/01a02aed-3d7c-7c80-b107-5e4985e839f0
repo_object_format: sha1
repo_head: a121cd821f7748f979c2cddf0f7c3af0e0b6a5a7
repo_branch: codex/online-oracle-mvp
worktree_kind: linked
artifacts:
  - .omx/context/online-oracle-mvp-20260822.md
  - .omx/plans/prd-online-oracle-mvp.md
  - .omx/plans/test-spec-online-oracle-mvp.md
  - .omx/plans/ralplan-handoff-online-oracle-mvp.md
  - .omx/specs/online-oracle-issue-acceptance.md
---

## Task

Plan the smallest owner-local implementation for persisted EVL-backed finite-
horizon Q_H inference, dense-valid round-based online learning, and a later
hierarchical bounded 5-DoF proposer ranked by that value model.

## Method

Graphify was rebuilt and verified fresh before design work. Live repository
owners, thesis gates, GitHub issues #54, #67-#77, #79-#82, and #89, and primary
research sources were inspected. Three codebase-design alternatives were
compared. The chosen plan then passed a sequential deliberate Ralplan lifecycle
after multiple Architect/Critic repair rounds.

Measured-autoresearch did not run: no explicit active mission, frozen evaluator,
or executable candidate existed. The plan separates mandatory WP0a functional
parity from a later mission-gated WP0b performance sidecar.

## Findings

- Reuse `QhActorTensors` and the injected `QhLightningModule` scorer seam.
- Add one production target-conditioned finite-horizon scorer plus a versioned
  immutable inference bundle; keep EVL frozen in the MVP.
- Put an identity-bound oracle episode facade over one extracted replay
  transition kernel. Preserve the current replay callback and selection DTOs;
  Q_H/oracle composition stays private to `oracle.pipelines`.
- Admit deployable online fitted Q only when dense-valid metadata and tensors
  prove labels for every actor-valid realized row. Canonicalize dense batches
  after padding without changing legacy padding behavior.
- Collect with one frozen behavior bundle into one new immutable shard, then
  refit and publish a new bundle. Collection persists no autograd graph.
- Defer hierarchical proposal until M5. Its runtime action is `K` categorical-
  family plus bounded local 5-DoF attempts; detached provenance reuses
  `CandidateSamplingResult.extras` and the existing serialization owner.
- Only scorer parameters must be differentiable for the MVP. Proposer
  likelihood gradients belong to a later AWR phase; score-function policy
  gradients must be recomputed during training; pathwise pose gradients and a
  surrogate are optional WP8 work. Hard oracle, masks, transitions, EVL,
  storage, and publication remain detached.

## Verification

- Architect iteration 6: approve, no P0/P1 findings.
- Critic iteration 3: approve, no P0/P1 findings.
- `git diff --check` passed for the planning artifacts.
- Graphify freshness must be rechecked after final artifact/index generation.
- The official host receipt verifier is unavailable. The handoff records
  `ralplan_consensus_gate.complete:false` with
  `documented_host_consensus_receipt_unavailable`; no source implementation,
  Ultragoal activation, or issue closure occurred.

## Canonical-state impact

No Python, configuration, test, thesis, or issue owner changed. These are
locally approved planning and handoff artifacts only. Execution must begin with
WP0a live issue/contract refresh after an official host-issued consensus receipt
is verifiable.
