---
id: 2026-06-21_zarr_python_skill_integration
date: 2026-06-21
title: "Zarr Python Skill Integration"
status: done
topics: [scaffold, skills, zarr, data-handling, rollouts]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/zarr-python/SKILL.md
  - .claude/skills/zarr-python
  - .agents/skills/dataset-cache-ops/SKILL.md
  - .agents/references/scaffold_routing_fixtures.json
---

## Task

Integrated a repo-local `zarr-python` skill as a compact ARIA-NBV routing and
evidence surface, while keeping `dataset-cache-ops` as the owner for dataset
operation, manifests, splits, smoke checks, and rebuild decisions.

## Method

Used the existing scaffold source-order and skill-style rules. The upstream
K-Dense Zarr skill was treated as community guidance, not as an ARIA source of
truth. Local package docs, module `AGENTS.md` files, package dependency metadata,
and official Zarr documentation remain the durable owners.

## Outputs

- Added `.agents/skills/zarr-python/SKILL.md` for Zarr-Python API, chunking,
  codecs, stores, sharding, concurrency, and migration work.
- Added the matching `.claude/skills/zarr-python` symlink without running the
  bulk sync script, because the current tree contains an unrelated stale symlink.
- Added a `dataset-cache-ops` handoff to `zarr-python` for Zarr API/storage
  changes.
- Added a routing fixture to protect Zarr API/storage changes from being routed
  as generic dataset operation.

## Verification

Run results are recorded in the session transcript. Required checks were
`make scaffold-audit`, `make check-agent-memory`, and `git diff --check` over
the touched guidance surfaces.

## Canonical State Impact

No canonical state files needed updates. This change adds a new repeatable
workflow skill and a scaffold routing fixture only.
