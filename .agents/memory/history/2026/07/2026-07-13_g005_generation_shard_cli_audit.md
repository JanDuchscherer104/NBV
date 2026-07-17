---
id: 2026-07-13_g005_generation_shard_cli_audit
date: 2026-07-13
title: "G005 Generation Shard CLI Audit"
status: done
topics: [oracle, rollouts, pipelines, cli, simplification]
confidence: high
canonical_updates_needed: []
---

# G005 Generation Shard CLI Audit

## Scope

Audited rollout generation, shard execution, manifest codecs, campaign status,
and existing-store inspection after the Oracle pipeline ownership moves.

## Decision

- `oracle.pipelines` owns generation composition, deterministic shard planning
  and execution, campaign status, and the build/plan/status CLIs.
- `rollouts` owns rollout and shard manifest codecs plus existing-store
  validation and inspection through `nbv-rollouts-info`.
- The two layers already compose through rollout-owned codecs; no formula,
  config, manifest, hash, or status implementation is duplicated.
- Removed two one-call forwarding adapters from `oracle.pipelines.shards` and
  routed their callers directly to `rollouts.shard_manifest`.

Production Python LOC decreased from 67,966 to 67,947 (-19).

## Verification

- Ruff, compileall, and the rollout writer/shard/CLI/info test suite passed.
- All five retained rollout/offline CLI help commands exited successfully.
- Static scans found no remaining forwarding-adapter callers.
- Independent exploration found the owner split coherent; independent
  architecture review marked the two forwarding-adapter deletions `CLEAR`.

## Canonical Updates Needed

- None. Package READMEs and CLI entry points already describe the active owner
  split.
