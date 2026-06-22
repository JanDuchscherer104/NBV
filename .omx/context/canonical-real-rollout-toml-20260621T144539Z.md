# Canonical Real Rollout TOML Context Snapshot

- Task statement: implement the approved canonical real rollout TOML plan.
- Desired outcome: `.configs/build_rollouts_v1_realistic.toml` is the single checked-in semantic default for real thesis rollout generation, with LRZ docs pointing operators to copy that canonical file for run-specific overrides.
- Known evidence: root `AGENTS.md`, `aria_nbv/AGENTS.md`, `aria_nbv/aria_nbv/rollouts/AGENTS.md`, `aria_nbv/aria_nbv/data_handling/AGENTS.md`, `docs/contents/theory/candidate_sampling_target_selection.qmd`, and `.configs/build_rollouts_v1_realistic.toml` were inspected. The current theory page defines `v1_realistic_3family` as 24 `forward_local`, 24 `target_bearing_local`, and 12 `lateral_target_bypass`, with 1.0m step, 0.25m height, 0.25m backward, and 70deg yaw limits.
- Constraints: preserve unrelated dirty worktree changes; avoid Q_H training settings; do not make LRZ-specific absolute paths canonical; keep Makefile `ROLLOUT_STORE ?= rollouts_v1_realistic.zarr`.
- Unknowns/open questions: local dry-run may depend on the availability of the VIN offline store and CUDA.
- Likely touchpoints: `.configs/build_rollouts_v1_realistic.toml`, `.configs/lrz/README.md`, and verification through `nbv-build-rollouts --dry-run`, rollout tests, ruff, and `git diff --check`.
