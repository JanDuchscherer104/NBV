---
id: 2026-08-26_candidate_generation_architecture_digest
date: 2026-08-26
title: "Candidate-generation architecture acceptance digest"
status: done
topics: [candidate-generation, provenance, architecture, rollouts]
confidence: medium
canonical_updates_needed: []
touched_owner_paths:
  - .omx/specs/autoresearch-rollout-candidate-diversity-pilot-20260824/report.md
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: ba5631d54379b5fd9f33ec072767524f52f5d97f
repo_branch: codex/pr116-candidate-provenance-salvage
worktree_kind: linked
---

## Purpose and source boundary

This is a compact tracked digest of accepted architecture decisions extracted
from the local, ignored raw review file
`.agents/work/target-architecture-spec-aggregatoion--2--08-24--gpt56pro.md` and
the ignored execution plan `.omx/plans/candidate-generation-issue-resolution-program.md`.
Those raw files are deliberately not promoted into this salvage PR. The
historical measurements and lineage details remain in
`.omx/specs/autoresearch-rollout-candidate-diversity-pilot-20260824/report.md`.
The clean replacement/disposition is [PR #153](https://github.com/JanDuchscherer104/ARIA-NBV/pull/153).

## Accepted source and candidate contracts

- The source identity is the V10 100-row/100-scene train manifest, with the
  retained hash-bound fields `605453ba11869e40` and
  `4780c7cde1b811bf`. Historical V8-bound V10-named shards are never relabelled.
- `CandidateSamplingResult` is the row-level seam. It retains attempted rows,
  hard-valid masks, reasons, margins, view residuals, and per-candidate
  `view_jitter_is_bounded`. The action shell contains valid rows; the audit
  retains the full attempted shell.
- Bounded box jitter preserves its configured dotted envelope. Legacy
  zero-cap `uniform_sphere`/`forward_powerspherical` support is uncapped, uses
  fixed yaw `[-180°,180°]` and pitch `[-90°,90°]`, keeps residuals visible, and
  has no fabricated rectangle.
- Canonical production profiles retain seminar jitter `60°/30°/0°`; the
  historical V11 plan delegates to the current writer and therefore does not
  reproduce the historical zero-jitter candidate contract.
- Proposal identity is keyed by physical selected history, target/task,
  contract, root/proposal replica, family, and draw round; selection identity
  is separate. No global CPU/CUDA RNG mutation or GT/oracle leakage is allowed.

## Accepted implementation sequence and live issue mapping

The replacement program is one self-contained PR per mechanism, with opt-in
challengers and unchanged production controls until the equal-compute gate:

| Work packages | Accepted action | Live issue anchors |
| --- | --- | --- |
| WP01-WP02 | Immutable benchmark bundle, applicability-aware family preflight, Phase A gate | #54, #73, #120 |
| WP03-WP06 | Durable proposal/selection keys, audit/action shell, bounded refill, Sobol/multi-root replicas | #68, #71, #117 |
| WP07-WP09 | Center/gaze factorization, orbit/standoff/peek/turn families, actor-safe sensing prescreen and micro-pairs | #69, #118 |
| WP10-WP12 | Typed node context, deterministic schedules, MPS artifact, empirical 5-DoF prior | #70 |
| WP13, WP16 | Unique-state proposal/render/score reuse, bounded oracle cache, renderer parity and throughput | #119 |
| WP14-WP15 | Camera/depth/unprojection and target-RRI robustness evidence | #79, #80 |
| WP17-WP18 | Confirmatory benchmark, phased pre-scale decision and promotion | #53, #81, #82, #120 |

Every WP must emit the existing candidate-panel/Plotly evidence, preserve
attempted-versus-valid/support-failure states, and report scene-level rather
than candidate-row statistical units. Reference reservoirs are bounded and
equal-compute; promotion is blocked by label validity, support, OOM, cache,
throughput, or worst-scene regressions.
