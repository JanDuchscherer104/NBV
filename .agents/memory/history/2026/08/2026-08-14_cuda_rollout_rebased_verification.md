---
id: 2026-08-14_cuda_rollout_rebased_verification
date: 2026-08-14
title: "CUDA rollout rebased verification"
status: blocked
topics: [rollouts, cuda, campaign, rebase, verification]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/campaign_generation.py
  - aria_nbv/aria_nbv/oracle/pipelines/campaign.py
  - aria_nbv/aria_nbv/oracle/pipelines/cli.py
  - aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py
  - aria_nbv/aria_nbv/oracle/target_selection.py
  - aria_nbv/aria_nbv/pose_generation/geometry.py
  - aria_nbv/aria_nbv/targets/selection.py
  - aria_nbv/tests/app/panels/test_campaign_generation_panel.py
  - aria_nbv/tests/oracle/test_campaign.py
  - aria_nbv/tests/oracle/test_target_selection.py
  - aria_nbv/tests/pose_generation/test_geometry.py
  - aria_nbv/tests/rollouts/test_cli_typer.py
---

## Task

Rebase the verified target seam, CUDA campaign core and hardening, and rich
Campaign Generation page onto the then-current `origin/main`; rerun all
evidence on the rebased tree; and close the mandatory Ultragoal quality gate
without launching the broad campaign or performing external GitHub writes.

## Method

Recorded pre-rebase commit `756e1030db00f9543fbfdd1c10c659704bcac0c0`,
fetched exact `origin/main` commit
`8323b8ed83867e1a2f0c754c7cf3025153b21c41`, and rebased without conflicts.
The initial rebased head was
`731b3c5b3642c9c4bb8ef3f4b95011e07adb2477`; all prior green results were
treated as stale. Adversarial review then repaired fail-closed target admission
and coordinate handling, campaign identity and lifecycle evidence, exclusive
claim ordering, watchdog output handling, operational bounds, status coverage,
and CLI error presentation. The changed-files AI-slop pass found no masking
fallback or needless abstraction requiring another edit; broad exception
handling remains confined to tested CLI/UI presentation boundaries, and
process-disappearance handling remains the tested watchdog fail-safe.

## Findings

The rebased campaign now keeps validation and execution ownership in
`aria_nbv/oracle/pipelines/campaign.py`, with the CLI and Streamlit page as
shallow adapters. CUDA and PyTorch3D validation pass on the local single NVIDIA
GeForce RTX 3080 Ti. Canonical config
`.configs/build_rollouts_v1_cuda_campaign.toml` has SHA-256
`13a0ea34fde1bde9a8444448348c9bf4b9001ee9c8545711da8b601696d356d1`,
and its typed writer digest is
`45932a47d90c79c05b278cb4cfd13548548739c89bd4695e57bd2deadcd973a7`.

The required real one-target smoke remains blocked before writes: the canonical
campaign requires 100 scenes, while the reviewed canonical source manifest has
50 rows across only five scenes and no reviewed 100-scene actor-visible
admission evidence exists. The canonical preflight exits 2 with
`source-target preflight requires 100 scenes; found 5`. The contract was not
relaxed and no evidence was fabricated.

## Verification

- Ruff format/check, compileall, and explicit-worktree `git diff --check`
  passed on the final rebased tree.
- The expanded target, campaign, CLI, Streamlit, writer, Zarr, public-API, and
  legacy configuration gate passed: 295 tests, 15 warnings.
- Canonical CLI `status --json` returned typed `not_started` status; canonical
  `preflight` and `plan` both fail cleanly at the reviewed five-versus-100 scene
  prerequisite without writes or tracebacks.
- The isolated CUDA/PyTorch3D child preflight passed on the RTX 3080 Ti.
- Independent code-reviewer verdict: APPROVE, no P0-P2 findings.
- Independent architect verdict: CLEAR; serial ownership, fail-closed writes,
  target seams, TargetLineage, target arrays, and Zarr schema remain intact.
- `make check-agent-memory` passed after this debrief was added.
- No broad rollout, push, pull request, issue, or other external GitHub write
  was performed.

## Canonical State Impact

None. Package code, tests, canonical TOML, and the durable Ultragoal ledger own
the implementation and blocker truth. No `.agents/memory/state/*.md` update is
needed; this file is the episodic debrief only.
