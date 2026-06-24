---
id: 2026-06-17_thesis_architecture_iteration15_fusion_value_head
date: 2026-06-17
title: "Thesis Architecture Iteration 15 Fusion Value Head"
status: done
topics: [thesis, architecture, q-h, set-transformer, value-heads]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - aria_nbv/aria_nbv/rl
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 15 adds a fusion and value-head contract for candidate-query `Q_H`.
The recommended architecture separates calibrated one-step target gain,
state-level finite-horizon value, zero-mean candidate advantage, and invalidity
masks instead of using a monolithic Transformer regressor.

## Evidence

- `docs/contents/theory/candidate_view_dependence.qmd` already recommends an
  independent calibrated base plus zero-mean set residual and residual-dueling
  `Q_H`.
- Local Set Transformer and Deep Sets sources support permutation-aware
  candidate-set baselines.
- Local QCNet/QCNeXt sources support query-centric relative encodings and
  typed interaction, while their driving-specific semantics remain out of
  scope.
- ArXiv primary-record lookup identified Wayformer, Perceiver, VectorNet, Scene
  Transformer, and HiVT-family leads as fusion/scalability references rather
  than immediate thesis-core dependencies.

## Canonical Updates Needed

- Move the fusion ladder and residual-dueling decomposition into the thesis
  method and evaluation chapters.
- Add implementation tests for absolute-head contamination, valid-row mean
  subtraction, invalid-row firewalling, token-source ablations, and early/late
  fusion comparisons.
- Decide whether Wayformer, Perceiver, VectorNet, Scene Transformer, and HiVT
  should become explicit `docs/literature/sources.jsonl` entries.
