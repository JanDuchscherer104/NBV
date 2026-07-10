---
id: 2026-07-10_wp07_target_ownership_lane
date: 2026-07-10
title: "WP07 Target Ownership Lane"
status: done
topics: [target-ownership, oracle, data-handling, rollouts]
confidence: high
canonical_updates_needed: []
---

## Task
Execute WP07 target-ownership preparation in `/home/jd/repos/ARIA-NBV-packages/target-ownership-wp07` without touching sibling worktrees, `.omx/ultragoal/**`, persisted sentinels, reason codecs, rollout schemas, or Zarr storage.

## Method
Used the 2026-07-09 architecture report as the contract, then combined Graphify availability checks, exact `rg`/AST ownership scans, targeted Ruff, py-compile, and pytest suites. Commits were kept staged as WP07a, WP07b, and WP07c.

## Findings
WP07a removed actor-visible target selector/source modes, TOML config branches, and live UI controls while preserving oracle task generation and persisted lineage fields.

WP07b added `aria_nbv.targets.descriptor.TargetDescriptor` as the only `aria_nbv.targets` root export and migrated real runtime consumers to use actor-safe target descriptors.

WP07c moved privileged GT target-task selection to `aria_nbv.oracle.target_selection`, moved GT OBB evidence lookup to `aria_nbv.oracle.evidence`, removed the `data_handling._target_selection` monolith/export, and simplified oracle task admission to finite positive GT geometry plus seeded uniform-without-replacement sampling. Legacy nullable identity fields remain only for lineage compatibility; the sampler no longer computes self-IoU scores or threshold sweeps.

## Verification
Validation used `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python` with `PYTHONPATH=/home/jd/repos/ARIA-NBV-packages/target-ownership-wp07/aria_nbv` because `uv run` in the package worktree is blocked by the uninitialized `external/efm3d` submodule metadata.

- Ruff: targeted touched-file checks passed for each WP07 commit.
- Tests: WP07a targeted suites passed with `53 passed` and `37 passed`.
- Tests: WP07b targeted suites passed with `91 passed` and `26 passed`.
- Tests: WP07c targeted suites passed with `151 passed`.
- Ownership scans: `targets_forbidden_imports []`, `data_handling_forbidden_edges []`, old `data_handling/_target_selection.py` removed, new oracle target-selection/evidence files present.

## Canonical State Impact
None. The code and tests now encode the WP07 ownership split; no `.agents/memory/state/*.md` canonical update was needed.
