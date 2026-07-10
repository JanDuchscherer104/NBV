---
id: 2026-07-09_rri_rollouts_oracle_pipelines_architecture_ralplan
date: 2026-07-09
title: "RRI Rollouts Oracle Pipelines Architecture RALPLAN"
status: done
topics: [aria-nbv, rri-metrics, rollouts, pipelines, architecture, ralplan]
confidence: high
canonical_updates_needed: []
artifacts:
  - .omx/context/rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md
  - .omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md
  - .omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-handoff-20260709T115007Z.json
  - .omx/specs/rri-rollouts-oracle-pipelines-architecture-review-20260709T115007Z.html
---

# RRI, Rollouts, Oracle, and Pipelines Architecture Ralplan

Date: 2026-07-09

## Summary

Created a revised planning handoff that supersedes the earlier
`rri_metrics`-only plan. The new plan includes the responsibility leakage
between `aria_nbv.rri_metrics`, `aria_nbv.rollouts`, and
`aria_nbv.pipelines`.

The approved direction is:

- keep `rri_metrics.oracle` as the owner of RRI oracle label semantics;
- do not create top-level `aria_nbv.oracle` until there is a second real oracle
  family;
- move scene/target rollout scorers, crop policy, invalidity, evidence
  assembly, and reward conversion into `rri_metrics.oracle`;
- keep `CounterfactualCandidateEvaluation` and `CounterfactualMetricBundle` as
  `rollouts`-owned replay adapter DTOs for the first implementation pass;
- move rollout writer/shard/CLI orchestration to
  `pipelines.rollout_generation`;
- narrow `rollouts` to replay state, transition expansion, Zarr storage,
  manifests, and read-side inspection;
- finish the smaller `rri_metrics` cleanup only after the cross-package seams
  are correct.

## Artifacts

- Context:
  `.omx/context/rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md`
- Plan:
  `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md`
- Visual review:
  `.omx/specs/rri-rollouts-oracle-pipelines-architecture-review-20260709T115007Z.html`
- Temp visual copy:
  `/tmp/architecture-review-rri-rollouts-oracle-pipelines-20260709T115007Z.html`
- Architect review:
  `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-architect-review-20260709T115007Z.md`
- Critic review:
  `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-critic-review-20260709T115007Z.md`
- Durable handoff:
  `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-handoff-20260709T115007Z.json`

## Evidence

- Graphify query showed the central cluster around rollout storage, scorer,
  writer, shard, pipeline, metric, app, and Rerun modules.
- `rollouts/AGENTS.md` still claims scorer and generation ownership, which is
  stale under the approved direction.
- `rollouts/target_counterfactuals.py` currently owns target crop policy,
  target invalidity, target/scenario scorer implementation, evidence caching,
  and reward conversion.
- `rollouts/dataset_writer.py`, `rollouts/shards.py`, and `rollouts/cli.py`
  currently own data-generation orchestration.
- `rri_metrics/oracle/scorer.py` and `rri_metrics/oracle/evidence.py` already
  own the base oracle RRI primitive and evidence sources.

## Consensus

- Architect: `APPROVE_WITH_CHANGES`; required explicit rollout DTO adapter seam
  and explicit `pipelines` package interface.
- Plan revised accordingly.
- Critic: `APPROVE`; no required edits.

## Validation

- Planning artifacts were created and checked for existence with the repo
  Python.
- The visual report was copied to `/tmp`; `xdg-open` failed because this
  environment has no browser/text opener installed.
- Package implementation code was not edited.
- Handoff JSON validation and `make check-agent-memory` are the remaining
  planning-surface checks for this session.

## Canonical Updates Needed

- When implementation starts, update `aria_nbv/aria_nbv/rollouts/AGENTS.md` so
  it no longer says rollouts owns target-aware oracle scorers, dataset writer,
  shard generation, or build CLI implementation.
- Add or update a `pipelines/AGENTS.md` if `pipelines.rollout_generation`
  becomes the owner for rollout build/plan/status orchestration.
- Regenerate Quarto/reference/context outputs after code moves.
