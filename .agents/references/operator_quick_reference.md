# Operator Quick Reference

Use this file for practical operator aids that do not belong in canonical
project state.

## Environment Recovery

- Preferred interpreter: `aria_nbv/.venv/bin/python`.
- Rebuild a missing or stale environment with `cd aria_nbv && uv sync --all-extras`.
- If Python 3.11 is not resolved automatically, set `UV_PYTHON` to a local
  interpreter for that command. Never put a host-specific interpreter path in
  shared guidance.
- Verify both `aria_nbv/.venv/bin/python --version` and
  `uv run python --version` before diagnosing dependencies.

## Repository Hygiene

Inspect `git status -sb`, `git diff --stat`, and `git diff --name-only` before
staging. Classify generated files before staging, stage by intent, and never
revert unrelated worktree changes unless explicitly requested.

## Frame And Key Conventions

- Frame hierarchy: world -> rig/device -> camera.
- Use `PoseTW` for poses and `CameraTW` for cameras.
- `T_A_B` means the transform from frame B to frame A.
- ATEK prefixes: `mtd` is motion trajectory data, `mfcd` is multi-frame camera
  data, and `msdpd` is multi-semidense-point data.

## EFM Snippet Views

- `camera_rgb`, `camera_slam_left`, `camera_slam_right` -> `EfmCameraView`
- `trajectory` -> `EfmTrajectoryView`
- `semidense` -> `EfmPointsView`
- `obbs` -> `EfmObbView` or `None`
- `gt` -> `EfmGTView`
- `mesh` / `has_mesh` -> optional ground-truth mesh

Use `.to(...)` on a snippet or sub-view to move tensors without cloning when
possible.
