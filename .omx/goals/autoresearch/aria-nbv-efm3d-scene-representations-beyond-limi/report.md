# ARIA-NBV Autoresearch: EFM3D Scene Representations Beyond EVL Voxel Extent

Date: 2026-06-22
Goal slug: `aria-nbv-efm3d-scene-representations-beyond-limi`
Verdict: pass

## Question

Which EFM3D-derived or EFM3D-compatible scene representations can give ARIA-NBV target/candidate/history features outside the fixed EVL voxel extent, without leaking oracle labels or assuming unavailable counterfactual RGB/DINO observations?

## Core Verdict

The best first representation is a sparse actor-visible semidense point bank augmented with compressed DINO descriptors sampled from logged observations.

This is higher ROI than making the EVL voxel grid larger because it preserves the strengths of EFM3D while fixing the wrong bottleneck. EFM3D/EVL is already a good local OBB/support anchor, but its local voxel field is not a complete long-horizon scene memory. A point-attached feature bank can span the broader semidense map, expose uncertainty/support/history, and be queried by target OBB, candidate frustum, and target-frustum intersection.

Do not generate fresh DINO at arbitrary candidate poses in the first design. Logged history has RGB/DINO; counterfactual candidate states do not, unless a renderable or learned feature generator is introduced and validated. Use selected successor geometry/support summaries for future steps, and keep oracle GT meshes, GT OBB crops, and all-candidate renders as labels/evaluation only.

## Evidence

### Local EFM3D Paper And Docs

- `docs/literature/tex-src/arXiv-EFM3D/method.tex:18-32` says EVL runs frozen DINO features on posed video, projects voxel centers into each image, samples 2D features, and aggregates across streams/time by mean and standard deviation.
- `docs/literature/tex-src/arXiv-EFM3D/method.tex:37-42` adds semidense point and freespace masks to the lifted voxel feature volume.
- `docs/literature/tex-src/arXiv-EFM3D/method.tex:104-108` fixes the common configuration around a 4 m cubical local volume with task-dependent resolution.
- `docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:263-266` explicitly names the limited 4 m x 4 m x 4 m viewing frustum as a limitation for distant geometry.
- `docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:310-313` reports egocentric 3DGS artifacts from user dynamics, so 3DGS/radiance fields should be bridge work, not the first thesis-core memory.
- `docs/contents/literature/efm3d.qmd:20-22` already frames EFM3D as actor-visible evidence and target support, not the whole planner memory.
- `docs/contents/literature/efm3d.qmd:37-40` already proposes semidense/fused points with compressed DINO features as the broader scene-memory hypothesis.
- `docs/contents/theory/efm3d_scene_embeddings.qmd:60-89` gives the planned token shape: world point, compressed DINO descriptor, uncertainty/confidence, observation count, and history metadata.
- `docs/typst/thesis/sections/03-method.typ:22-39` states the support mismatch: EVL reads are features plus coverage diagnostics, not proof of irrelevance.
- `docs/typst/thesis/sections/03-method.typ:72-112` already ranks semidense/fused point support, compressed DINO-on-point, EVL internals/crop reads, and later point/sparse encoders as the near-term ladder.

### EFM3D Source

- `external/efm3d/efm3d/model/image_tokenizer.py:36-74` wraps DINOv2 and can freeze it while exposing token feature dimensions and optional projection.
- `external/efm3d/efm3d/model/lifter.py:461-533` keeps `token2d`, `feat2d_upsampled`, `voxel/feat`, `voxel/counts`, `voxel/pts_world`, `voxel/T_world_voxel`, `voxel/selectT`, and `voxel/occ_input`.
- `external/efm3d/efm3d/model/evl.py:181-223` passes backbone outputs through the 3D neck and exposes `neck/occ_feat`, `neck/obb_feat`, `cent_pr`, `bbox_pr`, and `clas_pr`.
- `external/efm3d/efm3d/dataset/vrs_dataset.py:439-523` loads semidense global points, inverse-depth and depth uncertainty, observations, per-time point clouds, and all-points tensors.
- `external/efm3d/efm3d/dataset/vrs_dataset.py:583-604` loads padded snippet semidense point windows, which is enough for actor-visible support/history features.
- `external/efm3d/efm3d/inference/fuse.py:112-164` fuses local EVL volumes into a global volume; useful for occupancy/support, but less useful than point-attached DINO if the missing signal is visual/semantic target evidence.

### External Literature

- [EFM3D / EVL, arXiv:2406.10224](https://arxiv.org/abs/2406.10224): EVL is the correct Aria-native anchor because it uses egocentric streams, poses, calibration, semidense points, and 2D foundation features for 3D OBB/surface tasks.
- [DINOv2, arXiv:2304.07193](https://arxiv.org/abs/2304.07193): supports the choice of reusable dense visual features from a frozen foundation model.
- [OpenScene, arXiv:2211.15654](https://arxiv.org/abs/2211.15654): strong precedent for dense 3D point features co-embedded with image/text features; for ARIA-NBV, the lesson is point-attached features, not open-vocabulary semantics as a first goal.
- [ConceptFusion, arXiv:2302.07241](https://arxiv.org/abs/2302.07241): strong precedent for fusing pixel-aligned foundation features into a 3D map via SLAM/multi-view fusion.
- [LERF, arXiv:2303.09553](https://arxiv.org/abs/2303.09553): useful bridge for queryable feature fields, but too heavy and too easy to turn into a new renderable-memory thesis project.
- [Point Transformer V3, arXiv:2312.10035](https://arxiv.org/abs/2312.10035), [KPConv, arXiv:1904.08889](https://arxiv.org/abs/1904.08889), and [Minkowski ConvNets, arXiv:1904.08755](https://arxiv.org/abs/1904.08755): good later encoders after the point bank and simple masked pooling establish value.

## Ranked Options

| Rank | Representation | ROI | Risk | Adopt When |
| --- | --- | --- | --- | --- |
| 1 | Semidense/fused point bank + compressed DINO-on-point | Very high | Medium | First serious scene-memory ablation. |
| 2 | EVL internal/crop reads: `voxel/feat`, `neck/occ_feat`, `neck/obb_feat`, `feat2d_upsampled` | High | Low-medium | Use to test whether final EVL heads hide target/candidate evidence. |
| 3 | Semidense-only geometry/support/history bank | High | Low | Build as rung 1 and as the fallback if DINO storage is expensive. |
| 4 | Global fused EVL occupancy/support volume | Medium | Medium | Use for broad occupancy/support diagnostics, not as visual target memory. |
| 5 | Learned point/sparse encoder over the point bank | Medium-high | Medium-high | Escalate after simple masked pooling bottlenecks. |
| 6 | Sparse ray/keypoint DINO unprojection not tied to semidense tracks | Medium | High | Only after point-track joins are understood; depth uncertainty and duplication are hard. |
| 7 | LERF/3DGS/radiance-style feature field | Low-medium now | High | Defer as bridge work after Q_H replay and selected-depth summaries are credible. |

## Proposed First Implementation Experiment

Build a read-only feature extraction prototype before changing rollout schema:

1. Select a small set of ASE/ATEK samples with existing EVL inference products and semidense observations.
2. For each semidense point UID, gather logged observations where projection is valid and uncertainty passes existing MPS/ATEK filters.
3. Sample DINO feature maps from the logged frames only. Start from `rgb/feat2d_upsampled`; later compare raw `token2d` and EVL DPT head features.
4. Pool per-point features with support-weighted mean plus optional std/max, then compress to 32-128 dimensions with PCA or fixed random projection before any learned bottleneck.
5. Persist a candidate prototype artifact with point XYZ, point UID, inv/dist std, observation count, source frame ids or hash, DINO model id, compression id, and descriptor.
6. Query this bank by predicted/observed target OBB, candidate frustum, and target-frustum intersection. First use masked mean/max/count/empty indicators.
7. Compare against current EVL heads plus semidense scalar stats on one-step target-RRI ranking before wiring into Q_H.

Minimum diagnostics:

- Point count, observation count, and uncertainty distributions.
- Feature compression variance or random-projection norm preservation.
- Target OBB support count and empty-target rate.
- Candidate frustum support count, intersection support count, and out-of-EVL extent fraction.
- Leakage audit proving no GT mesh, GT OBB crop, oracle RRI, or all-candidate rendered depth enters actor descriptors.

## Inconsistencies And Open Decisions

- The thesis already says DINO-on-point is planned. It must remain planned/non-implemented until a writer/manifest/training reader exists.
- EFM3D supports local-to-global occupancy fusion, but this is not equivalent to global DINO feature memory. Do not present fused occupancy as solving visual target context outside EVL.
- Current Q_H descriptions correctly separate actor-visible and oracle state, but future feature-cache language must preserve that counterfactual states cannot access fresh candidate RGB/DINO.
- DINO compression policy is an open engineering/science choice. Raw 768-D per-point descriptors should not be the default.
- There is a likely thesis figure opportunity: EVL support box vs semidense map extent, with target/candidate query pools over target OBB, candidate frustum, and their intersection.

## Critic Verdict

Pass.

The conclusion is source-backed, conservative, and implementation-relevant. It does not overclaim DINO-on-point as implemented, does not merge actor inputs with oracle labels, and does not promote radiance/3DGS methods before the simpler point-bank ladder. The highest-ROI next work is a prototype feature-cache extraction and query experiment, not a new backbone replacement.
