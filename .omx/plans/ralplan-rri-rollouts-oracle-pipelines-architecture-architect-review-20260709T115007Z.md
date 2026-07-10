# Architect Review

Plan:
`.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md`

Agent: `019f46bf-0bf3-7332-b050-ccd1b49eb2a9`

Verdict: `APPROVE_WITH_CHANGES`

## Summary

The direction is sound: `rri_metrics.oracle` should own oracle label
semantics, `pipelines.rollout_generation` should own orchestration, and
`rollouts` should narrow to replay/storage/inspection. This matches the current
overload in `rollouts` and the existing `pipelines/oracle_rri_labeler.py`
precedent.

## Required Changes

1. Make the adapter seam explicit. The draft must state whether
   `CounterfactualCandidateEvaluation` and `CounterfactualMetricBundle` remain
   `rollouts`-owned replay adapters or are split into an oracle-return DTO plus
   replay DTO. The previous “unless implementation discovers” language was too
   soft because the DTO already has multiple consumers.
2. State the `pipelines` package interface at the module level.
   `pipelines.rollout_generation` should be named as the public home for
   build/plan/status, while `oracle_rri_labeler` remains the existing
   single-step pipeline.

## Steelman Antithesis

Moving scorer classes into `rri_metrics.oracle` improves semantic locality but
may not improve consumer locality if the actual adapter surface remains the
mixed `CounterfactualCandidateEvaluation`. If that DTO stays in `rollouts`, the
scorer move can become package shuffle plus import-cycle risk. A narrower move
of writer/shards/CLI into `pipelines` would preserve more leverage for the
existing replay adapter.

## Tradeoff Tension

- Better semantic depth in `rri_metrics.oracle` versus churn at the replay
  adapter seam.
- Cleaner ownership versus one stable DTO for existing consumers.
- Stronger separation of concerns versus the risk that `rri_metrics` starts to
  feel like orchestration rather than meaning.

## Synthesis

Keep the direction, but pin the seam:

- `rri_metrics.oracle` owns pure oracle scoring, evidence, crop, and reward
  semantics.
- `rollouts` owns the replay DTO and storage adapter.
- `pipelines.rollout_generation` owns orchestration and CLI.

