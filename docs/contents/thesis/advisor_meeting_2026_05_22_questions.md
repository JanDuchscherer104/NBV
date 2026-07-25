---
title: "Advisor Meeting Questions - 2026-05-22"
phase: thesis
audience: advisor
status: current
owner: jan
---

# Advisor Meeting Questions - 2026-05-22

Deck: `docs/typst/thesis_slides/advisor_meeting_2026_05_22.typ`

Meeting goal: align the thesis scope, research questions, and the next rollout / \(Q_H\) implementation gates before broad rollout data is generated.

## Questions To Show In The Deck

1. **RQ1 method:** Confirm the target-RRI objective, \(H\), \(\gamma\), \(\varepsilon\), clipping, near-solved target policy, and whether log gain is a primary companion metric or only a diagnostic.
2. **RQ2 offline \(Q_H\):** Confirm the success bar: positive oracle-lookahead headroom, recovered-headroom threshold \(\eta_Q\), matched oracle re-evaluation of learned selected actions, and fixed vs variable horizon.
3. **RQ3 representations:** Confirm that RQ3 owns the actor-visible representation ladder: semidense/fused geometry, sparse ray-aware occupied/free/unknown memory, EVL local/OBB evidence, target descriptors, \(S^2\) visibility memory, visibility-gated DINO descriptors, and candidate-to-state query features.
4. **RQ3 minimum path:** Which representation ablations are mandatory before interpreting \(Q_H\): ray-aware geometry, target crop descriptor, \(S^2\) visibility memory, visibility-gated DINO, candidate-to-state query features, or only a smaller first subset?
5. **RQ4 support:** Confirm the production candidate and rollout-support preflight: valid-count gate, target-aware family contribution, mixed target-centric/exploration support, regeneration after selected actions, scale support, and flat-reward blocker.
6. **RQ5 online discrete:** Confirm whether online discrete training over the same finite-candidate action contract is a gated follow-up after stable offline \(Q_H\), not a replacement for the offline evidence.
7. **RQ6 continuous headroom:** Confirm that continuous target-then-pose or hierarchical action spaces are tested only after discrete evidence and only for headroom over the best finite-candidate policy.
8. **Shared evidence protocol:** Confirm scene-level split / fallback, target matching thresholds, ambiguity handling, hard invalidity masks with reason codes, LRZ/Zarr preflight, and no GT actor-visible input.

## Questions To Ask, Not Necessarily Show

1. What minimal result would count as a successful master thesis if the full 100 GT-mesh ASE scenes / 4,608 snippets are blocked by storage, sharding, or compute?
2. Should the first representation pass prioritize sparse ray-aware occupied/free/unknown memory over EVL voxel/neck/head features and DINO descriptors because frustum support alone does not model visibility?
3. What compression target is acceptable for DINO-on-point storage: PCA, learned projection, product quantization, or a small learned token bank?
4. How fine should the target-local \(S^2\) visibility memory be: coarse histogram, low-order directional moments, or both as an ablation?
5. What target matching policy should resolve ambiguous observed/predicted OBBs: compatible class plus 3D IoU, support, projected area, distance, and confidence, or a stricter one-to-one rule?
6. Should target sampling be stratified by support / visibility / distance / class before any value-learning work, or can a robust softmax / top-\(K\) target sampler be enough for the first pass?
7. Which candidate families are mandatory before rollout scale-up: current valid/random/exploration, target-centric orbit/look-at views, information-overlap views, or late exploration variants?
8. What candidate-row interaction checks should gate \(Q_H\): independent scorer, candidate-to-state cross-attention, pooled DeepSets, masked Set Transformer, row-shuffle invariance, duplicate-row tests, valid-count stress tests, and mask-isolation tests?
9. Which online discrete method is scientifically justified first after offline \(Q_H\): online fitted Q updates on generated traces, DQN-style interaction over finite candidates, IQL-style conservative update, or another small bridge?
10. What would count as measurable continuous-action headroom over finite candidates without changing the target-RRI objective: better endpoint gain, higher \(\eta_Q\), lower path cost, or better coverage under equal oracle budget?
11. Which LRZ/Zarr gate must be non-negotiable before broad generation: production preflight JSON, stale-schema checks, chunk/file budget, shard grouping by scene split, or DSS retention policy?
12. Which qualitative failures should be shown in Rerun for advisor review: flat reward fields, invalid candidate collapse, target ambiguity, poor ray/DINO/semidense support, or Q policy overfitting to candidate family provenance?
