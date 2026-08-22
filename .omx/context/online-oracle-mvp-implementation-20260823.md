---
kind: implementation-status
slug: online-oracle-mvp
date: 2026-08-23
branch: codex/online-oracle-mvp
authorization: direct-user-request
---

# Online oracle MVP implementation status

The user directly authorized implementation after the locally approved Ralplan
handoff. This does not fabricate or replace the unavailable host-issued
consensus receipt, and no Ultragoal state was minted.

## Implemented

- WP0a CPU fixture: deterministic replay, Oracle-label, transition, endpoint,
  and stored-Q_H golden snapshot with `make replay-oracle-golden`.
- WP1: actor-only `TargetFiniteHorizonScorer`, closed config factory, masking,
  causal history/budget conditioning, candidate permutation equivariance, and
  scorer-parameter gradients.
- WP2: immutable Q_H experiment/bundle composition, validation-selected
  checkpointing with exact earliest-update tie-break, deterministic canonical resume payload, strict inference
  reconstruction, manifest/artifact verification, compatible-resume admission,
  receipts, and atomic publication.
- WP2a: dense-valid query/label/objective identities and post-padding tensor
  admission while preserving the legacy collation profile.
- WP5 foundation: identity-bound decision-context hashing, full-shell
  root-relative pose/table validation, stale nested-payload rejection, private
  inference-only Q_H-to-`CandidateScores` Adapter, persistence-neutral behavior
  bundle references, and frozen online-round request/result/count DTOs.

## Verification

- `make qh-ci PYTEST_WORKERS=0`: 393 passed.
- targeted mypy for the five new production modules: passed.
- changed-file Ruff format/check: passed.
- `make replay-oracle-golden`: passed with frozen source, configuration,
  contract, dependency, and numeric-tolerance identity.

## Gates still closed

- WP0a is not complete for promotion: no representative CUDA replay/oracle
  source bundle with mesh, target, source-manifest, renderer, and config hashes
  is locally available. The unrelated sample VRS is not promoted as evidence.
- WP4 replay-kernel/environment extraction remains blocked by the mandatory
  complete WP0a gate. The current change introduces only the context DTO needed
  by the scorer Adapter; it does not claim episode parity.
- WP5 collection/retraining remains blocked on WP4 plus the training-population
  manifest acceptance owned by the plan's issue matrix. No thin collector
  facade or synthetic shard promotion was added.
- WP3 and WP6-WP8 remain scientific/evidence work packages. No RQ5/RQ6 claim,
  hierarchical proposer, or pathwise refinement is implemented or promoted.
- WP0b measured-autoresearch is not activated because its prerequisite
  representative evaluator identity is unavailable.

## Promotion boundary

This branch is code-readiness evidence for the scorer, immutable bundle,
dense-valid admission, and detached online scoring seam. It is not evidence of
online-policy improvement, hard-oracle environment parity, or hierarchical
proposal quality.
