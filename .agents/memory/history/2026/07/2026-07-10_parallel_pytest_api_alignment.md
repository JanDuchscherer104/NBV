---
id: 2026-07-10_parallel_pytest_api_alignment
date: 2026-07-10
title: "Parallel pytest API alignment"
status: done
topics: [pytest, vin, mesh-cache, xdist]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/data_handling/mesh_cache.py
  - aria_nbv/tests/data_handling/test_mesh_cache.py
  - aria_nbv/tests/integration
  - aria_nbv/tests/rollouts
  - aria_nbv/tests/rri_metrics
---

## Task

Align stale tests with the current VIN scorer and candidate-depth renderer APIs,
remove unsupported real-data VIN integrations, and make processed mesh caching
safe for xdist workers.

## Result

Removed obsolete depth-renderer arguments and VIN integrations that invoke the
scorer without cached EVL evidence. Renamed duplicate public-API test modules.
Processed mesh cache access now uses a per-artifact Linux advisory lock,
atomic temporary-file publication, and rebuilds malformed cached PLY files.

## Verification

Ran focused Ruff, cache, public-API, scorer-boundary, and oracle-labeler tests;
all passed. Ran `cd aria_nbv && uv run pytest -n auto -q`; all 739 collected
tests completed without the original collection, depth-config, VIN, or PLY
cache failures.

## Canonical state impact

No canonical memory or guidance update is required. A real DSS-path
multi-process cache smoke remains a prerequisite before large Slurm generation.
