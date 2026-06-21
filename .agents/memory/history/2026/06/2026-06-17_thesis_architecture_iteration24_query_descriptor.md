---
id: 2026-06-17_thesis_architecture_iteration24_query_descriptor
date: 2026-06-17
title: "Thesis Architecture Iteration 24 Query Descriptor"
status: done
topics: [thesis, architecture, qcnet, descriptors, q-h, geometry]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - docs/contents/theory/rl_planning.qmd
  - docs/typst/shared/equations/features.typ
  - aria_nbv/aria_nbv/vin/pose_encoders.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 24 makes the planned QCNet-style component concrete. The transferable
idea is query-centric local-frame relative positional encoding between a query
candidate and candidate, target, history, or support tokens. The thesis should
not import QCNet/QCNeXt trajectory decoders, scene scoring, lane/agent priors,
DETR-style proposal matching, or streaming claims. The implemented
`R6dLffPoseEncoder` remains the first pose-control baseline; query-local RPE,
support-overlap bias, `S^2` directional memory, exact equivariance, and feature
bank joins are staged ablations.

## Evidence

- `docs/literature/tex-src/arXiv-QCNet/main.tex` documents the query-centric
  scene encoder: each scene element receives a local coordinate system and
  attention uses relative spatial-temporal positional embeddings relative to
  the query.
- The local QCNet TeX body is a QCNeXt technical report inheriting QCNet's
  encoder; it is useful for the encoder idea but not for ARIA trajectory
  decoding or scene-scoring claims.
- `aria_nbv/aria_nbv/vin/pose_encoders.py` implements `R6dLffPoseEncoder`,
  which encodes translation plus continuous 6D rotation in a documented
  reference frame through learnable Fourier features.
- `docs/typst/thesis/sections/03-method.typ` already separates R6D rotation
  features, QCNet-style candidate-local RPE, and `S^2` directional memory in
  the value-model method section.
- `docs/contents/thesis/questions.qmd` defines the minimum actor-visible target
  descriptor and keeps GT crops, GT mesh geometry, and GT OBBs out of V1 actor
  inputs.
- `.agents/work/proposal-review/s2-rpe-sh-overview.md` explicitly distinguishes
  RPE as a pairwise pose relation from `S^2`/spherical-harmonic directional
  memory as accumulated visibility history.
- A litkg hit for `docs/contents/impl/vin_v2_feature_proposals.qmd` pointed to
  a stale missing path and was not used as current evidence.

## Canonical Updates Needed

- Add a query-centric descriptor table to the thesis method chapter covering
  candidate self tokens, actor-visible target tokens, candidate-target
  relations, candidate-candidate RPE, candidate-history RPE, directional
  memory, and feature-bank joins.
- Preserve the R6D/LFF pose encoder as a required control before attributing
  gains to query-local RPE.
- Add anti-shortcut checks: raw-world pose ablation, with/without strategy
  provenance, row-order leakage, GT target leakage, RPE-vs-S2 separation,
  frame-convention drift, and scene-id memorization.
- When implementation begins, store canonical poses and identifiers first, then
  derive cached descriptors only with frame tags, source hashes, and schema
  versions.
- Keep the phrase "QCNet-style" scoped to local-frame RPE unless the thesis
  actually implements and validates a broader QCNet/QCNeXt component.
