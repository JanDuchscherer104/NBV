---
id: 2026-06-17_thesis_architecture_iteration22_data_product_contract
date: 2026-06-17
title: "Thesis Architecture Iteration 22 Data Product Contract"
status: done
topics: [thesis, architecture, rollouts, zarr, q-h, feature-cache]
confidence: high
canonical_updates_needed:
  - aria_nbv/aria_nbv/data_handling/README.md
  - .agents/references/rollout_zarr_q_invalidity_contract.md
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/rl_planning.qmd
  - .agents/work/rollout-scale-readiness/03-rollout-generation-preflight-plan.md
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 22 reconciles the planned architecture with the live rollout data
product. The thesis critique should no longer describe `rollouts.zarr` as
missing. The current implementation owns replay facts, target/candidate masks,
selected transitions, selected-depth audit artifacts, optional target-eval
crops, and a validated derived `q_h/` view. The remaining architecture risk is
boundary discipline: separate replay facts, training caches, audit-heavy
payloads, collection-level preflight gates, and future point-feature banks.

## Evidence

- `aria_nbv/aria_nbv/rollouts/zarr_store.py` defines the schema metadata,
  source/target/rollout/lineage/step/candidate tables, `selected_depth/`,
  `target_eval_crops/`, and the derived `q_h/` arrays.
- `validate_rollout_zarr_store` checks root metadata, persisted and derived
  `q_h/`, candidate masks, diagnostics, selected depth, target-eval crops,
  source/target lineage, and required target-RRI provenance.
- `aria_nbv/aria_nbv/rollouts/dataset_writer.py` writes standalone rollout
  stores from VIN roots, actor-visible targets, mixed candidate tables, target
  scoring, selected depth, lineage, and rollout recipes including random-valid,
  oracle-greedy, oracle-lookahead, and temperature-softmax.
- `aria_nbv/aria_nbv/data_handling/README.md` documents the two-store contract:
  immutable VIN offline samples remain separate from standalone
  `rollouts.zarr` counterfactual traces.
- `.agents/work/target-selection-sampling/02-review-gpt55pro.md` recommends
  separating `training_core` and `audit_heavy` retention profiles.
- `.agents/work/rollout-scale-readiness/03-rollout-generation-preflight-plan.md`
  describes a planned production preflight JSON with schema, validation,
  lineage, coverage, validity, rewards, retention, storage, and go/no-go
  sections.
- `aria_nbv/aria_nbv/rollouts/info_cli.py` currently exposes manifest,
  `--validate`, `--stats`, and `--random-index`, but not the proposed
  `--preflight --profile production --json` gate.
- `.agents/work/scene-encoding-efm-backbone/01-evl-critique-directions-gpt55pro.md`
  proposes `feature_lift_v1.zarr` as a separate point-attached feature artifact
  with source ids, point positions, observation counts, uncertainty, compressed
  DINO/optional CLIP/depth features, frame ids, and query pools.
- A stale subagent path under a nonexistent `aria_nbv/aria_nbv/cvrl/` tree was
  rejected after checking the local repo.

## Canonical Updates Needed

- Reconcile `.agents/references/rollout_zarr_q_invalidity_contract.md` with the
  live writer, validator, and data-handling README before treating it as current
  guidance.
- Add production preflight ownership: either extend `nbv-rollouts-info` with
  `--preflight --profile production --json` or document the chosen companion
  command.
- Add a collection-level manifest/check for shard aggregation, scene split
  purity, source-row coverage, candidate profiles, storage/chunk budgets, and
  stale-schema detection.
- Decide whether `feature_lift_v1.zarr` is the first feature-bank artifact and
  define its schema, compression, join keys, reader, and consumer tests.
- Make invalidity reason parity visible across writer, validator, inspector,
  preflight, and model training masks.
- In the thesis method/evaluation chapters, state that `q_h/` is a validated
  derived cache, while replay facts live in the rollout tables.
