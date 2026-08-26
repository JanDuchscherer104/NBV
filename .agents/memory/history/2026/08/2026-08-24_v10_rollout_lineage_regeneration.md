---
id: 2026-08-24_v10_rollout_lineage_regeneration
date: 2026-08-24
title: "VIN V10 Rollout Lineage Regeneration"
status: done
topics: [rollouts, vin, provenance, qh, campaign]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .configs/README.md
  - .configs/build_rollouts_v1_cuda_campaign_pilot_corrected_v11.toml
  - .configs/build_rollouts_v1_cuda_campaign_writer.toml
  - .configs/build_rollouts_v1_lrz.template.toml
  - .configs/rollout_campaign100_source_manifest.json
codex_thread: codex://threads/01a02e4d-39ed-7e43-99e0-6790460a36ff
repo_object_format: sha1
historical_repo_head: 52e9d262577260074bae25134fbd61c2bfda0533
historical_repo_branch: codex/fix-v10-rollout-lineage
current_truth_anchor: origin/main at salvage branch point db8c8812aca8fdae4be9565183e5e7ca66de53b6
repo_head: 52e9d262577260074bae25134fbd61c2bfda0533
repo_branch: codex/fix-v10-rollout-lineage
worktree_kind: linked
artifacts:
  - .data/offline_cache/rollout_supervision/campaigns/cuda-rollouts-v1-pilot-corrected-v11
---

## Historical task

Repair ten rollout shards excluded by Training Dataset because their persisted
source-manifest lineage did not match the selected VIN V10 root.

## Method

The selected VIN root and every affected rollout manifest were inspected before
changing configuration. The ten historical shards were valid rollout stores,
but were generated from VIN V8 (`ef88fa5940221922`) while the selected root was
VIN V10 (`605453ba11869e40`). Their sample identities were unchanged across VIN
versions, but rewriting their hashes would have falsified immutable provenance.

The canonical rollout source manifest and writer configurations were therefore
rebound to VIN V10, and a fresh `cuda-rollouts-v1-pilot-corrected-v11` campaign
was planned and executed at exact clean commit
`52e9d262577260074bae25134fbd61c2bfda0533`.

## Findings

- The application-side `source_manifest_hash_mismatch` was correct and remained
  strict; no validator or compatibility rule was weakened.
- The misleading `corrected-v10` campaign name did not imply VIN V10 lineage:
  its manifests explicitly recorded source cache version 8 and the V8 hash.
- Fresh regeneration was the smallest provenance-correct repair. The historical
  V8-bound stores remain inspectable but intentionally incompatible with VIN V10.

## Verification

- Campaign terminal state: 9 succeeded, 1 smoke shard reused, 0 failed,
  conflicted, timed out, blocked, or insufficient-support units.
- All 10 V11 stores passed `validate_rollout_zarr_store`.
- `build_dataset_bundle_summary(..., validate_rollouts=True)` returned `Ready`
  with zero findings against `vin_offline_rollout_campaign100_v10_rebuilt`.
- `build_qh_corpus_readiness` returned `Ready`: 40 train chains, 291 factual
  states, 8,415 trainable candidates, realized maximum horizon 8, and disjoint
  configured stages.
- A real two-chain DataLoader preview collated lengths 8 and 6 with truthful
  step/candidate padding and tensor shape `(2, 8, 60, ...)`.
- Focused tests passed (39), Ruff format/lint passed, and `git diff --check`
  passed. The broad campaign suite was separately proven green in the clean
  generation checkout; failures in the primary checkout were caused solely by
  unrelated concurrent dirtiness triggering the deliberate clean-revision gate.

## Canonical-State Impact

This debrief preserves the lineage repair as historical evidence. It does not
claim that terminal V11 status or the zero-jitter pilot is current truth. The
retained configs require source/store validation before reuse; no generated
store was available in this isolated checkout, so runtime store validation
remains a downstream gate. Current candidate generation is governed by the
replacement program and issues #117--#120.

At the historical commit, tracked rollout-generation configuration named VIN
V10 as the canonical source and the V11 pilot as the corrected campaign.
Generated V11 artifacts were the historical replacement training/inspection
corpus; no persistence schema or historical artifact was mutated. Current
promotion remains gated by the replacement program and exact source/store
validation.
