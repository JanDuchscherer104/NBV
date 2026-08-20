---
id: 2026-08-20_cuda_rollout_v10_gpu_headroom
date: 2026-08-20
title: "CUDA Rollout V10 GPU Headroom"
status: done
topics: [cuda, rollout-campaign, gpu-headroom]
confidence: high
canonical_updates_needed: []
---

## Task
Preserve at least 1.5 GiB of free RTX 3080 Ti memory during the corrected
five-target paired rollout pilot without changing its scientific workload.

## Method
Kept the reviewed 60-candidate, H=8, branch=1, beam=1, four-temperature
workload fixed and reduced only the writer-owned `max_views_per_batch`. The V9
pilot with a three-view batch was sampled every two seconds, then V10 repeated
the exact 10-unit paired plan with a two-view batch under the same sampler.

## Findings
V9 completed all 10 units but reached only 1,093 MiB free GPU memory, below the
1.5 GiB contract. The active writer configuration therefore changed
`max_views_per_batch` from 3 to 2 in
`.configs/build_rollouts_v1_cuda_campaign_writer.toml`, and the pilot identity
advanced to V10 in
`.configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v10.toml`.

V10 completed with 3,608 MiB minimum free GPU memory. Its 10 validated stores
contain 40 rollout/Q_H chains, and every store contains nonzero trainable Q_H
rows. No candidate count, profile, horizon, branching, beam, temperature,
schema, or generation algorithm changed.

The terminal audit also exposed that elapsed time was not reconstructible from
the canonical event ledger. The campaign now writes one measured duration to
both the `campaign_finished` event and terminal status, reconstructs status
from that evidence, and rejects divergence. This changes observability only,
not rollout generation or persisted dataset contents.

## Verification
- Focused Campaign tests, Ruff format/check, agent-memory validation, and hosted
  Root Verification passed.
- Canonical V10 status: completed; 1 validated smoke skip, 9 successes, zero
  failed, timed-out, insufficient, blocked, conflicted, or pending units.
- Independent two-second sampler: `min_free_mib=3608`, `max_used_mib=8306`.
- Canonical Zarr and Q_H audit: 10/10 stores valid, 40/40 chains readable,
  every store has nonzero trainable Q_H rows.
- Terminal elapsed-time regressions: completed status retains the exact ledger
  duration, event-only reconstruction agrees, tampering fails closed, and
  legacy null-elapsed ledgers use their timestamp-derived fallback.

Exact commit, plan, generation, work-unit, row-count, and raw sampler receipts
remain with the current campaign artifacts under
`aria_nbv/.campaign/cuda-rollouts-v1-pilot-corrected-v10/`; this debrief records
the durable batch-size decision without duplicating mutable run identity.

## Canonical Owner Impact
The writer TOML owns the two-view execution batch. The V10 campaign TOML and
`.configs/README.md` own the reproducible operator identity and command surface;
`aria_nbv/aria_nbv/oracle/pipelines/campaign.py` owns truthful terminal status,
and `aria_nbv/tests/oracle/test_campaign.py` locks both contracts. No further
canonical update is needed.
