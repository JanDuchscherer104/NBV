---
id: 2026-06-17_thesis_architecture_iteration26_feature_bank_escalation
date: 2026-06-17
title: "Thesis Architecture Iteration 26 Feature Bank Escalation"
status: done
topics: [thesis, architecture, feature-bank, point-transformer, kpconv, sparse-conv, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/efm3d_scene_embeddings.qmd
  - docs/contents/theory/candidate_view_dependence.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 26 turns point-cloud backbones into an explicit escalation gate rather
than a default architecture direction. The thesis-core scene encoder should
start with typed actor-visible target, frustum, and target-frustum-intersection
pools over semidense/fused support and compressed DINO@point features. Point
Transformer, PTv3, KPConv, and Minkowski-style sparse convolution become late
support-encoder ablations only after compact query pools fail a localized
representation-bottleneck test and after provenance, invariance, density, and
runtime/storage contracts pass.

## Evidence

- `docs/contents/theory/efm3d_scene_embeddings.qmd` already defines EVL as
  local actor-visible target/support evidence and semidense/fused points as the
  broader queryable scene memory, with compressed DINO@point as the first
  serious scene-embedding hypothesis.
- `.agents/work/scene-encoding-efm-backbone/01-evl-critique-directions-gpt55pro.md`
  recommends EVL OBBs plus semidense geometry and lifted DINO features, then a
  separate `feature_lift_v1.zarr` with target/candidate query pools.
- `docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex` motivates
  local vector attention, kNN neighborhoods, and learned relative position
  encoding for point sets, which is useful only if local point interactions are
  the bottleneck.
- `docs/literature/tex-src/arXiv-Point-Transformer-V3/section/3_method.tex`
  shows PTv3's scalability tradeoff: serialization and patch attention reduce
  kNN/RPE cost but make ordering and serialization provenance explicit model
  contracts.
- `docs/literature/tex-src/arXiv-KPConv/egpaper_final.tex` motivates
  radius-neighborhood kernel point convolution for irregular point support and
  density variation, while deformable kernels add regularization debt.
- `docs/literature/tex-src/arXiv-MinkowskiEngine/sections/3_preliminary.tex`
  and `sections/4_minkowskiengine.tex` show that sparse convolution depends on
  quantization, coordinate hashing, kernel maps, sparse pooling, and voxel
  ownership decisions.
- `make kg-search KG_QUERY='point feature bank DINO point transformer KPConv Minkowski scene support encoding feature_lift_v1 target frustum pool'`
  surfaced canonical Point Transformer / PointNeXt literature and stale
  archived PointNeXt integration notes, confirming that active thesis guidance
  should prefer the current report and theory pages over archived wrappers.

## Canonical Updates Needed

- Add the feature-bank escalation gate to the thesis method/evaluation chapters:
  compact query pools first, point/sparse backbones only after localized
  representation-bottleneck evidence.
- Decide whether `feature_lift_v1.zarr` is the exact artifact name and schema
  owner for compressed DINO@point, frame/source lineage, support counts,
  uncertainty, projection validity, and feature schema hashes.
- Add evaluation checks for point-order shuffle, source dropout,
  support-stratified calibration, feature schema hash invalidation, kNN/radius
  or serialization sweeps, voxel-origin audits, and storage/runtime reporting.
- Keep `rollouts.zarr` as replay truth and `feature_lift_v1.zarr` as a separate
  actor-visible feature artifact joined by stable sample ids and schema hashes.
