# PR 23 Apple-Silicon Mojo context

## Activation prompt / task seed

Make GitHub PR #23 run natively on the user's Apple-Silicon Mac for VIN-store generation, multi-step rollout-dataset generation, rendering, and pose generation. Use Mojo at the existing Python-importable kernel seams, iteratively benchmark and simplify, retain only verified improvements, and continue until independently reviewed and adversarially QA-checked.

Original task status: `activation-prompt`.

This snapshot captures the Autopilot activation prompt and initial evidence. It is not guaranteed to contain prior conversation context beyond the current request.

## Desired outcome

- PR #23 is runnable end-to-end on arm64 macOS without CUDA-only runtime requirements in the requested data-generation paths.
- Python remains orchestration; Mojo owns only high-leverage numeric kernels inside a maintained PyTorch3D fork, parallel to the corresponding CPU/CUDA operators.
- VIN-store and multi-step rollout artifacts are generated on the Mac and pass schema/scientific contract checks.
- Rendering and pose generation execute natively and preserve shape, dtype, coordinate-frame, mask, reason-code, CLI/config, and persisted-schema contracts.
- Runtime and implementation LOC are measured; only positive, verified experiments are kept.
- Independent code-reviewer and architect gates are clean, followed by adversarial dynamic QA and a professor-critic pass.

## Known facts / evidence

- Local host is macOS 26.4.1 on `arm64`; OMX 0.18.16 and Codex CLI 0.144.3 are installed.
- The original workspace was an empty Git repository. PR #23 was fetched into worktree `/Users/jd/Documents/Aria-NBV/macos-pr23` on branch `codex/pr23-apple-silicon` at `2b5095e`.
- PR #23 targets `aria-nbv-refactor` and is currently a mergeable draft. Its reported fresh data-generation validation is CUDA-only.
- An older donor branch (`3ceeff9`, `origin/dev`) contains repo-local Python-importable Mojo modules for pose generation, rendering, and RRI metrics. Those files are reference/parity donors only under the later user override; they are not the target ownership location.
- Project-scoped OMX/native-agent tooling was installed and verified in the parent workspace. The actual repo retains its own root `AGENTS.md` contract and project skills.
- The current upstream Matt Pocock skill bundle was installed under `.agents/skills/` in the worktree, including `improve-codebase-architecture`.
- `ssh ubuntu` currently times out in the configured proxy before authentication, so the remote `~/repos/ARIA_NBV` checkout has not yet been inspected or changed.
- Durable Autoresearch mission: `.omx/goals/autoresearch/pr23-apple-silicon-mojo/mission.json`.
- Active Codex goal uses the same professor-critic completion rubric.

## Constraints

- Native Apple-Silicon execution is required; CUDA cannot be a runtime prerequisite for the requested workflows.
- Preserve public/config/checkpoint/Zarr/scientific contracts unless a failing native constraint proves a narrowly scoped change necessary.
- Implement Mojo inside a maintained PyTorch3D fork beside its CPU/CUDA operator implementations, and keep ARIA-NBV integration limited to pinning/configuration and public PyTorch3D calls.
- Prefer deletion and reuse; add no dependency unless evidence proves it necessary.
- Do not broadly rewrite optimized PyTorch operations or Python I/O/orchestration.
- Preserve unrelated work and existing PR #23 behavior.
- Continue autonomously through safe local edit/test/benchmark loops; stop only on explicit user interruption or a hard external/credential blocker.

## Decision boundaries and working assumptions

- User override (2026-07-13): Mojo implementations belong inside a PyTorch3D fork, parallel to PyTorch3D's CUDA implementations. ARIA-NBV must not own duplicate repo-local Mojo kernels.
- “Using Mojo” means the fork's native compute kernels replace or complement CUDA-shaped PyTorch3D operators while Python/ARIA orchestration remains Python.
- Prefer CPU Mojo first when buffers are already host-resident or control flow is branch-heavy; use Mojo Metal only when transfer-amortized workload evidence supports it.
- Small generated fixtures and reduced rollout counts are acceptable for the first e2e proof, provided the same production CLI/config/schema path is exercised.
- Safe simplifications directly supporting native execution, lower LOC, or clearer ownership may be applied without another approval pause.

## Unknowns / open questions

- Exact first failing install/import/runtime command on this Mac.
- Which requested paths are blocked by dependency metadata versus CUDA-only code branches.
- Whether current Mojo modules compile against the installed/current Modular toolchain and Python version.
- Minimal real-data or hermetic fixture needed for a native VIN-store plus multi-step rollout e2e run.
- Whether Metal improves any target enough to justify additional code over CPU Mojo.
- Whether the SSH proxy route recovers in time to synchronize the remote working checkout.

## Likely codebase touchpoints

- `aria_nbv/aria_nbv/pose_generation/`
- `aria_nbv/aria_nbv/rendering/`
- `aria_nbv/aria_nbv/rri_metrics/`
- `aria_nbv/aria_nbv/oracle/pipelines/offline_vin.py`
- `aria_nbv/aria_nbv/oracle/pipelines/rollout_dataset.py`
- `aria_nbv/aria_nbv/data_handling/offline/`
- `aria_nbv/pyproject.toml` and lock/environment files
- Existing Mojo parity tests and benchmark scripts under `aria_nbv/tests/` and `aria_nbv/scripts/`
- Apple-Silicon implementation notes under `docs/contents/impl/`
- A local worktree/clone of the authenticated user's PyTorch3D fork, with operator sources, build metadata, and tests colocated with upstream CPU/CUDA implementations

## Repo rules and context inspected

- `AGENTS.md`
- `.agents/skills/agent-behavior/SKILL.md`
- `.agents/skills/simplification/SKILL.md`
- `.agents/skills/aria-nbv-context/SKILL.md`
- user-level `mojo-nbv-acceleration/SKILL.md`
- PR #23 metadata and file list from GitHub

Prompt-safe initial-context summary status: `not_needed`.
