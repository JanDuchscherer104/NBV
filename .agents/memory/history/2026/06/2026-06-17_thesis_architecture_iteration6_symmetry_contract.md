---
id: 2026-06-17_thesis_architecture_iteration6_symmetry_contract
date: 2026-06-17
title: "Thesis Architecture Iteration 6 Symmetry Contract"
status: done
topics: [thesis, literature, geometric-deep-learning, equivariance, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by refining the planned candidate-query
`Q_H` architecture against geometric invariance/equivariance literature and the
repo's current theory/work notes.

## Findings

The first `Q_H` model should not claim full geometric equivariance by default.
It should use the exact symmetries that the task requires: candidate-row
permutation equivariance, local-frame relative geometry, explicit hard masks,
and actor/oracle separation. Global origin and arbitrary yaw should be
quotiented out with root/current/target/query-local frames, while physically
meaningful symmetry-breaking signals such as gravity/up, camera pitch, frustum
geometry, support density, and target ambiguity should remain available.

EGNN, SE(3)-Transformer, e3nn spherical harmonics, Point Transformer, PTv3,
KPConv, MinkowskiEngine, and gauge-equivariant mesh CNNs are useful ablations or
representation backbones only after the simpler finite-candidate value contract
is measured. The strongest default is a scalar invariant/local-frame feature
model with row-equivariant candidate-set interaction and typed local RPE.

Local theory and work notes also require a readiness risk register: target-local
frame consistency, support-field leakage, invalidity-mask semantics, and
`rollouts.zarr` lineage/preflight checks must be proven before architecture
complexity is used to explain results.

## Canonical State Impact

The autoresearch report now includes an explicit symmetry contract, exact
equivariance escalation rule, module boundary table, and thesis wording
recommendation for the value model. Follow-up thesis edits should add a method
subsection and evaluation tests for row shuffle, duplicate rows, mask isolation,
valid-count stress, candidate-family shifts, and frame consistency.

## Verification

- Local TeX scans covered Geometric Deep Learning, EGNN, SE(3)-Transformer,
  Point Transformer, PTv3, KPConv, and MinkowskiEngine.
- Literature metadata confirmed e3nn spherical harmonics is a URL-only source in
  `docs/literature/sources.jsonl`.
- Repo scans covered `rri_theory.qmd`, `candidate_view_dependence.qmd`,
  `candidate_sampling_target_selection.qmd`, `rl_planning.qmd`, and `.agents/work`
  rollout/target-selection notes.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
