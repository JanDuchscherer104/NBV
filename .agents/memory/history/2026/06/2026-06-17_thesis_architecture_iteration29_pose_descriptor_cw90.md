---
id: 2026-06-17_thesis_architecture_iteration29_pose_descriptor_cw90
date: 2026-06-17
title: "Thesis Architecture Iteration 29 Pose Descriptor And CW90 Contract"
status: done
topics: [thesis, architecture, pose-encoding, r6d, qcnet, cw90, geometry]
confidence: high
canonical_updates_needed:
  - docs/typst/shared/equations/features.typ
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_view_dependence.qmd
  - aria_nbv/tests/vin/test_vin_model_v3_methods.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 29 resolved the local architecture question about whether candidate
pose features should use R6D+translation or QCNet-style descriptors. The answer
is a ladder, not a replacement: R6D+LFF remains the default per-row pose token;
QCNet-style query-local relative positional encoding is the relation-aware
candidate-set ablation; shell SH is a shell-profile pose ablation; directional
visibility memory remains separate selected-history state; CW90 is an explicit
correction/display boundary.

## Evidence

- `R6dLffPoseEncoder` imports `matrix_to_rotation_6d`, forms `[translation,
  R6D]`, and validates a 9D LFF input:
  `aria_nbv/aria_nbv/vin/pose_encoders.py`.
- VIN v3 documents and implements the path
  `T_r_cq = (T_w_r)^-1 @ T_w_cq -> (t, R6D) -> LFF -> pose_enc`, then combines
  the pose token with voxel, semidense, and optional trajectory context:
  `aria_nbv/aria_nbv/vin/model_v3.py`.
- The trajectory encoder uses the same R6D+LFF pose family:
  `aria_nbv/aria_nbv/vin/traj_encoder.py`.
- The shell SH encoder consumes center direction, forward direction, radius,
  and alignment, and explicitly does not encode roll about the forward axis:
  `aria_nbv/aria_nbv/vin/experimental/spherical_encoding.py` and
  `aria_nbv/aria_nbv/vin/experimental/pose_encoders.py`.
- Pose generation derives yaw/pitch from a sampled forward direction and builds
  a roll-free rotation by default; roll jitter is a separate local-forward roll:
  `aria_nbv/aria_nbv/pose_generation/orientations.py`.
- QCNet/QCNeXt supports the query-centric transfer: local coordinate systems
  plus relative positional embeddings for attention, not the trajectory decoder
  or road-scene task:
  `docs/literature/tex-src/arXiv-QCNet/main.tex`.
- The shared equation draft already contains both R6D pose tokens and
  query-local RPE equations, with a TODO asking whether one should replace the
  other:
  `docs/typst/shared/equations/features.typ`.
- CW90 is a local `+Z` roll/twist correction with "apply once" guidance;
  candidate generation applies it to the reference pose, plotting defaults avoid
  applying it again, and VIN v3 fails closed when correction is requested without
  a corrected-camera tag:
  `aria_nbv/aria_nbv/utils/frames.py`,
  `aria_nbv/aria_nbv/pose_generation/candidate_generation.py`,
  `aria_nbv/aria_nbv/pose_generation/plotting.py`, and
  `aria_nbv/tests/vin/test_vin_model_v3_methods.py`.

## Canonical Updates Needed

- Update `docs/typst/shared/equations/features.typ` so the TODO becomes an
  explicit descriptor ladder: R6D/LFF row token plus query-local RPE relation
  features.
- Add thesis method wording that distinguishes canonical stored poses, derived
  row pose tokens, relation descriptors, shell SH pose ablations, and selected
  directional-memory features.
- Add or keep tests for R6D continuity/round-trip, global translation/yaw gauge,
  CW90 fail-closed behavior, corrected PoseTW+camera semantic parity,
  PyTorch3D/PoseTW row-vector convention, shell no-roll sensitivity, RPE row
  equivariance, and descriptor-source dropout.
