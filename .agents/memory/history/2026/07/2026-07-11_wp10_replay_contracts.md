---
id: 2026-07-11_wp10_replay_contracts
date: 2026-07-11
title: "WP10 Replay Contracts"
status: done
topics: [rollouts, replay, policy, architecture]
confidence: high
canonical_updates_needed: []
---

# WP10 Replay Contracts

## Scope

Introduced the minimal rollout replay boundary without changing Oracle scoring,
persisted Zarr schemas, or rollout-selection behavior.

## Changes

- Moved the replay engine to `aria_nbv.rollouts.replay.engine`.
- Added immutable `RolloutPolicySpec` as the single owner of rollout policy
  configuration.
- Added `CandidateScores` as the compact score-and-mask contract consumed by
  replay selection.
- Moved replay state DTOs and state helpers to `rollouts.replay.state`.
- Kept Oracle adapters at pipeline and application composition edges; the
  replay package has no Oracle dependency.
- Migrated canonical rollout TOMLs to nested `recipes.policy` tables.
- Kept existing Zarr arrays, reason-code values, CLI command names, and rollout
  behavior unchanged.

## Verification

- Ruff check and format check over touched Python files.
- Python compilation over package and test modules.
- Full affected rollout, Oracle, Streamlit panel, configuration, and public API
  tests.
- Canonical rollout TOML parsing and smoke CLI dry run.
- Stale-path and forbidden-dependency scans.
- Quartodoc reference regeneration and Graphify update.
- Independent architecture and code-review gates before commit.

## Follow-Up

WP11 must split the transitional wide evaluator result into Oracle candidate
labels, retained evidence, and the pipeline-local aggregate. The wide evaluator
DTOs remain in the replay engine only until that contract is introduced.

## Canonical Updates Needed

- None. This work implements the ownership roadmap already recorded in the
  canonical module-pruning report.
