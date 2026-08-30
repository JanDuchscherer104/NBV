# Historic local worktree inventory

Recorded 2026-08-29 against `origin/main` `fae1b1b08e31978fd16234d1f32f090738ad0403`. No historic worktree was modified or removed during this audit.

| Worktree | Branch / PR | Relative to current main | Local state | Disposition |
| --- | --- | ---: | --- | --- |
| `macos-pr23` | `codex/pr23-apple-silicon`; closed, unmerged [PR #25](https://github.com/JanDuchscherer104/ARIA-NBV/pull/25) | 1,175 behind, 18 unique commits ahead | modified checkpoint/Rerun binaries; untracked `.venv 3` | Primary Mojo salvage source. Reconstruct selected changes on current main; never merge/cherry-pick the full 199-file PR. Preserve the working environment until the fresh Mac bootstrap is independently reproducible. |
| `graphify-main-repair` | `codex/graphify-main-repair`; merged [PR #26](https://github.com/JanDuchscherer104/ARIA-NBV/pull/26) | 1,125 behind, 0 ahead | clean | Already delivered. No salvage. Safe removal candidate only after the user chooses to prune worktrees. |
| `graphify-docstrings` | `codex/graphify-docstrings`; no unique branch commits | 1,177 behind, 0 ahead | modified thesis PDF plus untracked memory, plan, figures, slides, `.DS_Store`, and `tmp/` | Branch history has nothing to merge, but untracked/modified documentation artifacts require a separate keep/archive/discard review before pruning. Not relevant to Mojo. |
| `rri-datasets` | `codex/rri-dataset-adapters`; upstream ref gone, no matching PR found | 1,176 behind, 0 ahead | 19 modified tracked files, 549 additions / 76 deletions | High-risk uncommitted work, not branch history. Preserve intact. Audit as a separate data-contract salvage effort; do not conflate it with Mojo backend work. |
| repository umbrella root | `master`, unborn/zero commit checkout | not comparable | contains linked worktrees and local infrastructure | Retain as a worktree container. Use `main/` as the canonical clean checkout for development. |

## PR #25 salvage contents

Keep or reconstruct:

- immutable Mojo-enabled PyTorch3D fork selection;
- build isolation/runtime Torch ABI matching;
- Apple Clang `-Wno-invalid-specialization` compatibility scoped to the affected toolchain;
- one global geometry backend/device seam;
- deterministic candidate/rollout selection fixes where current main still needs them;
- frozen fixture digests, backend counters, operator parity, VIN/rollout profiles, benchmark methodology, and raw evidence schemas.

Do not replay:

- vendored Matt Pocock skills or old agent scaffold files;
- generated `.omx` state and historic workflow plans as code changes;
- stale lockfile/config paths without re-resolving against current main;
- the unrelated merge commit in the PR;
- broad per-call-site backend changes.

## Additional source: `origin/dev`

Commit `3ceeff` (`Add Mojo oracle accelerator backend`) is a secondary evidence mine. It changes 77 files and adds package-owned backend modules across pose generation, rendering, RRI, pipelines, subprocess handling, and UI/controller surfaces. Salvage only provider-level kernels, parity/hostile tests, probes, profiling, and provenance ideas. Its ARIA-internal backend architecture conflicts with the desired one-seam design and should not be merged wholesale.

## Safe cleanup order after salvage

1. Make the new Mac provider setup reproducible without relying on `macos-pr23`'s environment.
2. Export or commit any intentionally retained `rri-datasets` diff onto a current-main branch after a dedicated review.
3. Classify and archive wanted `graphify-docstrings` artifacts.
4. Remove only clean/fully archived linked worktrees through `git worktree remove`; never delete their directories directly.
