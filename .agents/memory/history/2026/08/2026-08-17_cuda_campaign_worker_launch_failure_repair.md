---
id: 2026-08-17_cuda_campaign_worker_launch_failure_repair
date: 2026-08-17
title: "CUDA campaign worker launch failure repair"
status: done
topics: [cuda, rollout-campaign, recovery]
confidence: high
canonical_updates_needed: []
---

## Task
Diagnose the broad CUDA campaign's rapid terminal failures, repair the launch
contract surgically, resume the immutable plan, and verify sustained progress.

## Method
Correlated `status.json` and ordered `progress.jsonl` with process evidence,
traced worker argv construction into `subprocess.Popen`, reproduced the
failure with an empty `PATH`, then replaced the console-script dependency with
the active absolute Python interpreter and module dispatch.

## Findings
The campaign completed nine units before the `nbv-rollout-campaign` console
script became unavailable. Each remaining `Popen` failed before producing a
PID and the record-and-continue policy recorded 352 failures in under one
minute. `aria_nbv/aria_nbv/oracle/pipelines/campaign.py` now launches workers
through `sys.executable -m aria_nbv.oracle.pipelines.cli --campaign`; the CLI
module owns that internal dispatch in
`aria_nbv/aria_nbv/oracle/pipelines/cli.py`. Commit `8f2039b0` contains the
repair and focused regressions. The exact external action that removed the
generated console script is not present in campaign evidence.

## Verification
Focused campaign and CLI tests passed (184 tests), Ruff format/check and
`git diff --check` passed, and the module entrypoint succeeded with an empty
`PATH`. Exact-SHA CUDA preflight passed. The resumed campaign promoted two
consecutive new units (96.9 s and 231.4 s), both Zarr stores validated with no
errors, and a third serial worker reached 100% GPU utilization with no new
failure or timeout.

## Canonical State Impact
None. Runtime truth remains in the campaign status, event ledger, immutable
plan, and promoted shard evidence under `.campaign/cuda-rollouts-v1/`.
