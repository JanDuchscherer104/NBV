---
id: 2026-06-17_thesis_architecture_iteration16_scene_support_encoding
date: 2026-06-17
title: "Thesis Architecture Iteration 16 Scene Support Encoding"
status: done
topics: [thesis, architecture, scene-encoding, efm3d, q-h]
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

Iteration 16 adds a scene/support encoding contract. It keeps EFM3D/EVL as
actor-visible local target/support evidence and OBB provider, while making
semidense/fused points with compressed lifted image features the first serious
queryable scene-memory ablation for candidate-query `Q_H`.

## Evidence

- `docs/contents/literature/efm3d.qmd` says EVL is actor-visible evidence and
  target support, not a planner or complete scene memory.
- `docs/contents/theory/efm3d_scene_embeddings.qmd` identifies semidense/fused
  points plus compressed DINO@point features as the first serious scene
  embedding hypothesis and defines target/frustum/intersection query pools.
- `.agents/work/scene-encoding-efm-backbone/01-evl-critique-directions-gpt55pro.md`
  independently recommends EVL OBBs plus semidense/DINO point state before a
  broad scene-representation replacement.
- Local Point Transformer, KPConv, PTv3, and MinkowskiEngine sources motivate
  point/sparse encoders only as later ablations with explicit density,
  quantization, frame, and runtime contracts.

## Canonical Updates Needed

- Move the scene/support representation ladder into thesis method prose.
- Decide whether to create a `feature_lift_v1.zarr` or equivalent point-feature
  cache for compressed DINO@point and candidate-query pooling experiments.
- Add tests for EVL extent splits, source dropout, point-order invariance,
  density stress, frame transforms, predicted-depth separation, sparse
  quantization sensitivity, and storage/runtime cost.
