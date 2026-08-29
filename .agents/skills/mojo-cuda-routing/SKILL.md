---
name: mojo-cuda-routing
description: Route ARIA-NBV backend work that must stay portable between Mac Apple Silicon Mojo experiments and Ubuntu CUDA/PyTorch3D production runs.
---

# Mojo CUDA Routing

Use this skill for ARIA-NBV changes involving PyTorch3D, CUDA rollout generation, Apple Silicon, Mojo, renderer/provider selection, or cross-host parity between the local Mac and `ssh ubuntu ~/repos/ARIA-NBV`.

## Routing Contract

CUDA on Ubuntu is the default lane. Treat PyTorch3D CUDA behavior, rollout campaign contracts, and real-data CI evidence from Ubuntu as the production reference unless the user explicitly scopes work to a Mac-only experiment.

Mac Apple Silicon is the small-experiment lane. It may use a Mojo-compatible PyTorch3D provider or another ARIA-owned fork, but callers inside `aria_nbv` should still speak PyTorch3D-shaped interfaces: tensors, `Meshes`, `PerspectiveCameras`, rasterizer fragments, and point-face distances. Put provider selection in packaging, setup, preflight, or a narrow internal adapter; keep model, oracle, rollout, and data modules backend-neutral.

Record provider identity whenever the backend can affect scientific output: source repository, commit SHA, platform, Torch version, device, and whether the run used CUDA, CPU, MPS, or a Mojo provider. Reject ambiguous provenance for generated rollouts, benchmark artifacts, or cross-host comparisons.

## Implementation Shape

1. Open the local owner first: `aria_nbv/pyproject.toml`, renderer/preflight modules, focused tests, and the relevant worktree setup script. Use Ubuntu only to validate the CUDA lane or to inspect already-authoritative artifacts.
2. Keep the public interface stable. Prefer platform markers, local setup scripts, and narrow preflight helpers over `if mojo` branches spread through `aria_nbv`.
3. Preserve CUDA strictness. CUDA tests and campaign checks should fail when CUDA/PyTorch3D is unavailable or silently downgraded.
4. Preserve Mac usefulness. Mac setup should install a known provider, run CPU/small renderer smoke tests, and make the selected provider visible through a preflight/provenance command.
5. When comparing lanes, run the smallest real-data case available on both hosts and compare invariant outputs or documented tolerances rather than assuming kernel-level equality.

## Context7

For external API facts or version-sensitive library behavior, read [Context7 backend queries](references/context7-backend-queries.md). Use the exact library IDs from the repo-local `aria-nbv-context` registry when present; resolve missing IDs through Context7 before querying.
