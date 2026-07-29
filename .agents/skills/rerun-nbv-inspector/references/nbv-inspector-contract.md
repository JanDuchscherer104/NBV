# ARIA-NBV Rerun Inspector Contract

Use this reference before changing or reviewing:

- `aria_nbv/aria_nbv/rerun_inspector/`
- `aria_nbv/tests/rerun_inspector/`
- `aria_nbv/aria_nbv/data_handling/_offline_visual_inventory.py`
- `.configs/inspection/rerun/rerun_offline.toml`
- generated API docs under `docs/reference/`

## Purpose

The inspector is a visual trust diagnostic for immutable VIN offline-store
samples. It should reveal frame mistakes, candidate ordering bugs, invalid
candidates, missing optional fields, suspicious RRI labels, and geometry
misalignment before those samples are used for VIN training or rollout evidence.

It must not recompute labels, mutate samples, train models, or silently fall
back to online datasets.

## Required Sample Inputs

Validate these before Rerun initialization:

- `sample_key`, `split`, `scene_id`, `snippet_id`
- `vin_snippet.points_world` and `vin_snippet.lengths`
- `oracle.reference_pose_world_rig`
- `oracle.candidate_poses_world_cam`
- `oracle.p3d_cameras`
- `oracle.candidate_count`
- `oracle.rri`
- RRI component tensors used for accuracy/completeness deltas

Missing optional fields should appear as metadata warnings, not guessed payloads.

## Candidate Semantics

- Candidate tensors are fixed width; `candidate_count` is the valid prefix.
- Padded rows after `candidate_count` must not be visualized as real candidates.
- `mask_valid` refines validity within the prefix when present.
- A no-candidate sample should produce no candidate frusta, no centers, and no
  top-oracle layer.
- An all-invalid sample may show invalid frusta if configured, but no
  top-oracle layer.
- Candidate labels should include stable ids and, when available, RRI/validity.

## Geometry Semantics

- Candidate poses are world-from-camera: `T_world_cam`.
- Reference poses are world-from-rig: `T_world_rig`.
- Candidate cameras are native `Transform3D` + `Pinhole` entities when the
  logger has tests for transform direction and camera convention.
- Display-only CW90 corrections must operate on copied output arrays only.
- Downsampling must be deterministic and display-only.
- Mesh and OBB logging is diagnostic; GT mesh is not a training payload.

## Output Contract

The CLI should support:

- `--config-path`
- split/index selection
- sample-id selection
- save, spawn, and connect output modes

The saved smoke command is:

```bash
cd aria_nbv
uv run nbv-rerun-inspect --config-path ../.configs/inspection/rerun/rerun_offline.toml \
  --split val --index 0 --save ../.artifacts/rerun/sample.rrd
```

If the local offline store is version-blocked, report the exact reader error
and keep the failure linked to the offline-store issue instead of weakening
validation.

## Tests To Prefer

- Fake-Rerun tests that assert sink setup happens before logging.
- Public CLI override tests.
- Inventory tests that fail before Rerun when required fields are missing.
- Frustum endpoint tests with synthetic `PoseTW`/`CameraTW`.
- Candidate-count and all-invalid tests for no misleading top-oracle output.
- Depth/RGB tests that distinguish 2D diagnostics from camera-context depth.
