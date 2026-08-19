---
id: 2026-08-19_g003_producer_contract_repair
date: 2026-08-19
title: "G003 producer contract repair"
status: partial
topics: [campaign, rollout, provenance, candidate-generation]
confidence: high
canonical_updates_needed: []
---

# G003 Producer Contract Repair

## Changes

The producer lane now enforces D2 root admission at 15 in the campaign and
campaign writer configuration, persists separate campaign/source split fields,
and records deterministic unit and recipe seed lineage. Path-collision
generation evidence distinguishes applicable, evaluated, and detected masks.
Promotion owner and success sidecars now include a deterministic content hash
covering the promoted Zarr/manifest payload, and resume validation recomputes
that hash. Rollout Zarr, source-manifest, shard-manifest, campaign-plan, and
admission-audit contracts were bumped and reject stale artifacts.

## Verification

- Focused campaign and pose-generation tests: 182 passed.
- Ruff check passed on all touched Python files.
- Python compile checks passed for touched pipeline/rule modules.
- `git diff --check` passed.

## Scope Note

The full six-slice G003 producer program remains partial: detector/GT V1
selection policy expansion, explicit TARGET_POINT/MotionRealism boundary audit,
100-scene exclusion-ledger plumbing, and broad generation/store regeneration
were not attempted because their exact approved owner contracts were not
available in this worker lane. G004 lifecycle and inspection consumers were
left untouched.
