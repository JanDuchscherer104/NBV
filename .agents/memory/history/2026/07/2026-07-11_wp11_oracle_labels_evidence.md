---
id: 2026-07-11_wp11_oracle_labels_evidence
date: 2026-07-11
title: "WP11 Oracle Labels and Evidence"
status: done
topics: [oracle, rollouts, replay, lineage, architecture]
confidence: high
canonical_updates_needed: []
---

# WP11 Oracle Labels and Evidence

## Scope

Separated Oracle labels and optional heavy evidence from rollout replay state
without changing selection behavior, CLI names, or persisted Zarr schemas.

## Changes

- Added Oracle-owned `OracleCandidateLabels`, `RetainedOracleEvidence`, and
  `OracleCandidateEvaluation` contracts with compact-row validation.
- Added the pipeline-local evaluated-rollout aggregate and the adapter that
  projects Oracle evaluations to replay-owned `CandidateScores`.
- Removed Oracle metric vectors, point clouds, target crops, and selected-depth
  payloads from replay transitions and trajectories.
- Replaced the wide rollout write record with a structural writer protocol and
  a pipeline-owned `EvaluatedRolloutRecord`.
- Composed rollout lineage from source, target, and policy components; only the
  Zarr writer flattens those fields into the frozen storage schema.
- Preserved selected-depth and target-crop retention as explicit evidence
  profiles and migrated Streamlit/Rerun consumers to the evaluated sidecar.
- Removed obsolete wide evaluator/result exports and regenerated API
  navigation.

## Verification

- Ruff format/check and Python compilation over all touched Python files.
- `178` affected Oracle, rollout, Rerun, Streamlit, and public API tests.
- Compact-label ordering and evidence-row validation regression coverage.
- Rollout smoke CLI dry run and all retained CLI help commands.
- Frozen Zarr schema validation, stale-symbol scans, dependency-boundary scan,
  Quartodoc regeneration, and Graphify update.
- Independent architecture and code-review gates before commit.

## Follow-Up

WP12 can now complete the remaining generation-pipeline ownership work. The
rollout dataset writer, shard runner, and CLI already live under
`oracle.pipelines`; the remaining substantive move is the scene labeler still
under the temporary top-level `pipelines` package.

## Canonical Updates Needed

- None. This work implements the ownership roadmap already recorded in the
  canonical module-pruning report.
