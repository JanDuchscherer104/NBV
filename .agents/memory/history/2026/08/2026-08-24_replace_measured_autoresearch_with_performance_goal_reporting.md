---
id: 2026-08-24_replace_measured_autoresearch_with_performance_goal_reporting
date: 2026-08-24
title: "Replace measured autoresearch with performance-goal reporting"
status: done
topics: [autoresearch, performance-goal, wandb, streamlit, scaffold]
confidence: high
canonical_updates_needed:
  - .agents/references/human_owner_intent.md
  - .agents/skills/agent-behavior/SKILL.md
  - aria_nbv/aria_nbv/performance_checkpoint.py
  - aria_nbv/aria_nbv/configs/wandb_config.py
  - aria_nbv/aria_nbv/app/panels/wandb.py
touched_owner_paths:
  - .agents/references/human_owner_intent.md
  - .agents/skills/agent-behavior/SKILL.md
  - aria_nbv/aria_nbv/performance_checkpoint.py
  - aria_nbv/aria_nbv/configs/wandb_config.py
  - aria_nbv/aria_nbv/utils/wandb_utils.py
  - aria_nbv/aria_nbv/app/panels/wandb.py
codex_thread: codex://threads/01a0347c-583c-74c1-ad74-b67d5f78326a
repo_object_format: sha1
repo_head: dab7e62c1558acfbec28f3d907154878288dd21f
repo_branch: "codex/intent-candidate-capture"
worktree_kind: linked
---

## Task
Replace the standalone measured-autoresearch sidecar with an OMX performance-goal result bridge and read-only W&B inspection.

## Method
Validated one immutable version-one evaluator result, derived a SHA-256 evidence identity, optionally mirrored it to W&B, then sent its concise evidence to OMX's existing checkpoint command.

## Findings
- Removed the sidecar and its custom ledger script; `$performance-goal` now owns the evaluator lifecycle.
- Added [`aria_nbv/aria_nbv/performance_checkpoint.py`](../../../../../aria_nbv/aria_nbv/performance_checkpoint.py) and its explicit CLI wrapper for validation, W&B mirroring, and OMX checkpointing.
- Reused [`aria_nbv/aria_nbv/configs/wandb_config.py`](../../../../../aria_nbv/aria_nbv/configs/wandb_config.py) for non-Lightning W&B run identity; the existing W&B panel renders only explicit bridge records without history fetches.

## Commits
- [821a9309ccb01c4c5639ce92bafc14b975f41d92](https://github.com/jdgalviss/ARIA-NBV/commit/821a9309ccb01c4c5639ce92bafc14b975f41d92) — immutable-result bridge, W&B inspection, and sidecar retirement
- [92ba133873ba80d741b67c2d8aefca71b003076d](https://github.com/jdgalviss/ARIA-NBV/commit/92ba133873ba80d741b67c2d8aefca71b003076d) — preserve hard-gate, checkpoint, and byte-snapshot invariants
- [e61562e8fc9dcb2d9e98f026e9acf8d5a58f18b0](https://github.com/jdgalviss/ARIA-NBV/commit/e61562e8fc9dcb2d9e98f026e9acf8d5a58f18b0) — anchor OMX checkpointing at the repository root

## Verification
Passed focused Ruff and pytest checks (14 tests), `scripts/tests/test_agent_governance_g002.py`, and `make check-agent-memory`. An authenticated smoke evaluator read one persisted rollout shard, checkpointed its verified 17-link/1,920-candidate provenance result, and logged that result plus two inspection Plotly figures to W&B.

## Canonical Owner Impact
Updated the explicit human intent, agent-behavior routing, W&B configuration and inspection owners, plus their focused tests. No thesis claim changed.
