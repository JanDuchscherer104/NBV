---
id: 2026-08-18_qh_reader_factual_chain_repair
date: 2026-08-18
title: "Q_H Reader Factual Chain Repair"
status: done
topics: [qh, rollouts, reader, zarr]
confidence: high
canonical_updates_needed: []
---

## Task

Repair Q_H reader chain boundaries for packed stores containing early-terminal
trajectories without changing the writer, Zarr schema, or public reader DTOs.

## Method

Added a production-shaped fixture that truncates typed trajectories to factual
lengths `[3, 1, 2]` before writing through `write_rollout_zarr_store`. Replaced
configured-horizon slicing with one ordered factual `steps/rollout_row_id`
cursor pass, validating non-empty ownership, contiguous step indices, horizon
bounds, and orphan rejection. Derived `horizon_remaining` from configured
horizon minus persisted `steps/step_index`.

## Findings

Before the repair, the regression failed with reader lengths `[4, 2, 0]`
instead of `[3, 1, 2]`. The repaired reader returns the factual lengths and
preserves budgets `[4,3,2]`, `[4]`, and `[4,3]`. Parameterized regressions also
cover missing, interleaved, and orphaned rollout ownership while bypassing the
canonical validator with a previously successful validation result.

## Verification

- Source-bound `tests/rollouts/test_qh_reader.py`: 23 passed.
- Leader integration rerun: 23 passed in 36.25s.
- Ruff format/check passed on both owned Python files.
- `git diff --check` passed.
- Downstream Q_H seam was run by the leader against the shared edits; its
  result is recorded in the task handoff.

## Canonical-state impact

No canonical state or generated artifact was changed. The worktree contained
pre-existing unrelated campaign, agent, and quarantine artifacts; they were
preserved and excluded from the focused commit.

## Files touched

- `aria_nbv/aria_nbv/rollouts/qh_reader.py`
- `aria_nbv/tests/rollouts/test_qh_reader.py`
