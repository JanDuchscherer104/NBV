# CUDA-default / Mojo-compatible backend salvage plan

## Outcome

Keep Linux/CUDA as ARIA-NBV's production default while making Apple Silicon a reproducible, lower-throughput lane for deterministic tests, agentic experiments, and research loops. Backend selection must not spread through `aria_nbv`: the package continues to call public PyTorch3D interfaces, and PyTorch3D owns CPU/CUDA/Mojo operator dispatch.

## Current evidence

- The clean macOS worktree is `/Users/jd/Documents/Aria-NBV/main` at `origin/main` commit `fae1b1b08e31978fd16234d1f32f090738ad0403`.
- Current `origin/main` pins official PyTorch3D in `aria_nbv/pyproject.toml`; Linux Torch wheels remain selected by platform markers.
- A clean official PyTorch3D build against Torch 2.4.1 fails on current Apple libc++ because Torch specializes a non-specializable standard type trait. A cached build also exhibited a Torch ABI mismatch.
- The retained fork `/Users/jd/Documents/Aria-NBV/pytorch3d-mojo` at `0b213747a5610e56e8be5c0c7a11fca67a883018` builds on this Mac, imports `_C` and `_mojo`, preserves the public PyTorch3D API, and exposes immutable capability/provenance status.
- The provider passes 25 focused Mojo point-mesh/raster/status tests, including 34 subtests. Current ARIA integration passes 19 focused geometry/Q_H tests with one expected xfail plus the real scene-81283 pose/render/backprojection/Oracle-RRI test.
- Closed, unmerged ARIA PR #25 contains the original dependency pin, a single geometry-device seam, deterministic parity fixtures, benchmark methodology, and E2E profiles. It also contains obsolete agent scaffolding and generated OMX artifacts that must not be replayed.
- `origin/dev` commit `3ceeff` contains useful Mojo kernels, probes, profiles, and tests, but introduces package-internal backend modules across pose generation, rendering, RRI, pipelines, subprocess handling, and the UI. It is evidence to mine, not a commit to merge.

## Architectural decision

PyTorch3D remains the deep module and compatibility boundary:

```text
ARIA configuration / environment
          |
          +-- geometry device policy: auto | cuda | mojo | cpu
          |
          +-- ordinary public PyTorch3D calls
                         |
                         +-- CUDA adapter (upstream _C, production default)
                         +-- Mojo adapter (fork-private dispatch, Darwin arm64)
                         +-- CPU reference adapter (upstream _C)
```

The preferred distribution policy is:

- Linux: official/pinned CUDA-capable PyTorch3D provider, `auto` resolves geometry to CUDA when available.
- Darwin arm64: immutable Mojo-enabled PyTorch3D fork provider, `auto` may select eligible Mojo forwards on CPU tensors.
- Explicit `cuda`, `mojo`, and `cpu` modes fail early when unavailable or when an input violates the selected backend's contract.
- Checkpoint/model device selection stays independent from geometry backend selection.

No `if mojo` or Mojo imports are allowed in pose generation, rendering, RRI, VIN, rollout, or model code. The only acceptable ARIA product-code seam is one central geometry-device resolver plus backend provenance/preflight reporting.

## Options considered

### A. Platform-selected PyTorch3D-compatible provider — adopt

ARIA pins/selects a provider, while the provider implements private backend dispatch behind existing PyTorch3D operations. This has the smallest package surface and keeps CUDA behavior intact.

### B. ARIA-owned geometry/render protocol — defer

A new adapter protocol could isolate PyTorch3D, but today it would be a shallow wrapper over a broad third-party API and would require changes across cameras, meshes, rendering, point-mesh distance, and tests. Reconsider only if the fork can no longer track required PyTorch3D contracts.

### C. Merge the `origin/dev` Mojo backend — reject

This maximizes ARIA-owned branching, subprocess policy, and duplicate geometry behavior. Salvage its tests, kernels, probes, and benchmark ideas selectively; do not merge or cherry-pick the backend commit wholesale.

## Salvage matrix

| Source | Keep | Rework | Discard |
| --- | --- | --- | --- |
| PR #25 | immutable fork pin; runtime/build Torch ABI match; Apple compiler compatibility; one global geometry backend value; deterministic fixture digests; operator/VIN/rollout parity tests; backend counters; benchmark methodology | refresh dependency markers and lockfile against current `origin/main`; port only current config/test locations; regenerate evidence on current hardware | vendored `.agents`; `.omx` state/plans as implementation; old merge commit; stale paths/configs; broad unrelated PR diff |
| PyTorch3D fork `0b213747` | private `_mojo_ops` dispatch; direct Mojo extension; point-face/face-point/raster forwards; build fixes; fork tests; public backend status | keep its patch series anchored to the selected PyTorch3D lineage; document capability matrix and maintenance policy | unrelated upstream history and generated benchmark outputs |
| `origin/dev` `3ceeff` | parity fixtures; hostile input cases; provenance/preflight concepts; subprocess timeout/error tests; benchmark profiles; any kernel improvements proven against fork implementation | move useful implementation into the PyTorch3D fork, preserving public operations; translate tests to provider-level tests where possible | `aria_nbv/*/mojo_backend.py`; Mojo branches in product modules; UI/backend plumbing; duplicated package-owned kernels |
| stale local worktrees | evidence and branch metadata | none unless unique commits appear after future fetch | `graphify-docstrings` and `rri-dataset-adapters` as salvage sources: both are 0 commits ahead and over 1,100 commits behind current main |

## Delivery phases

### Phase 1 — Preserve and reproduce the Mac lane

1. Record the fork SHA, Mojo 1.0.0b2 toolchain, Python 3.11, Torch 2.4.1, macOS deployment target, and Apple compiler workaround in an environment bootstrap script or documented command.
2. Build the fork with runtime Torch rather than an unconstrained isolated build dependency.
3. Add a two-process import smoke for `pytorch3d._C`, the Mojo extension, camera imports, point-face distance, and restricted rasterization.
4. Make the platform-specific provider reproducible through lock/source selection or a dedicated Mac extra/lock. Do not make Linux resolve the Mojo toolchain.

Exit: a fresh Darwin arm64 environment builds without cache dependence and `nbv-cli --help` plus focused pose/render tests pass.

### Phase 2 — Rebase and shrink the provider fork

1. Rebase/cherry-pick the fork's functional commits onto the exact PyTorch3D base selected by current ARIA.
2. Keep dispatch in a private provider module; keep public PyTorch3D signatures unchanged.
3. Define the Mojo capability profile explicitly: CPU-contiguous float32 geometry, int64 offsets/counts, forward/no-grad, and the restricted hard-depth raster settings ARIA uses.
4. Make forced backends strict and `auto` permissive. Unsupported Mojo inputs fall back only in `auto` and increment observable counters.
5. Run the fork's point-mesh and raster suites, including degeneracy, ties, non-contiguous tensors, gradients, near-plane clipping, and unsupported settings.

Exit: the fork diff is reviewable, every fallback is intentional and counted, and CPU/CUDA reference behavior is unchanged.

### Phase 3 — Surgical ARIA integration

1. Select the provider by platform without introducing backend imports into `aria_nbv`.
2. Port only the central geometry-device resolver concept from PR #25. Keep generic model/checkpoint device handling backend-blind.
3. Add a small preflight/provenance record containing requested backend, resolved backend, provider URL/SHA, Torch version, device, and provider counters.
4. Keep existing callers such as `pose_generation/geometry.py` on public PyTorch3D operations.
5. Lazily import optional heavy renderer surfaces where necessary so CLI/config/research utilities fail at the first required capability rather than package import time.

Exit: deleting the central resolver/provider selection removes all ARIA-specific backend logic; no product call site contains Mojo branches.

### Phase 4 — Cross-backend equivalence

1. Freeze non-tied operator fixtures with stable digests and run the same fork SHA on Mac CPU/Mojo and Ubuntu CPU/CUDA.
2. Require exact integer outputs; compare float outputs with recorded mismatch count, max absolute error, and max relative error. Start with `rtol=2e-5`, `atol=2e-6` for operators and justify any looser end-to-end tolerance.
3. Run pose pruning, candidate depth rendering, RRI, a minimal VIN-store build, and a deterministic horizon-2 rollout on both hosts.
4. Compare schemas, lineage, masks, selected rows, and persisted-store reopening exactly; compare poses/depth/scores within declared tolerances.
5. Record hardware-qualified absolute timings. Do not publish a direct Mojo-vs-CUDA speed ratio across different machines.

Exit: equivalence evidence identifies the exact provider SHA and fixture digest, and forced modes prove the intended backend executed.

### Phase 5 — Overnight Mac research profile

1. Add a bounded Mac profile using CPU geometry/Mojo operators and MPS only for model operations already supported by Torch.
2. Default to small synthetic or cached real fixtures, deterministic seeds, bounded trials, checkpointed outputs, resume support, timeouts, and disk quotas.
3. Separate correctness experiments from performance experiments; store environment and backend provenance with every artifact.
4. Treat full CUDA-scale training, OpenPoints CUDA extensions, and high-throughput dataset generation as Ubuntu-only.
5. Add an overnight smoke that can complete without network access and leaves a concise success/failure summary.

Exit: an unattended Mac run can resume after interruption, cannot silently fall back from forced Mojo, and produces comparable, provenance-rich artifacts.

## Acceptance criteria

1. On Ubuntu, default configuration continues to select CUDA and passes the existing CUDA tests without environment changes.
2. On Darwin arm64, a documented locked setup builds the pinned fork from a clean cache and imports twice.
3. `PYTORCH3D_BACKEND=mojo` proves nonzero provider counters for point-face, face-point, and restricted rasterization; unavailable/unsupported forced modes fail early.
4. Outside the central resolver and preflight/provenance surface, `rg -n 'mojo|PYTORCH3D_BACKEND' aria_nbv/aria_nbv` returns no backend policy.
5. Pose, render, RRI, minimal VIN, and horizon-2 rollout parity pass against frozen fixtures and declared tolerances.
6. Serialized experiment outputs record requested/resolved backend, provider URL/SHA, device, Torch version, host hardware, seed, and fixture digest.
7. Mac `nbv-cli --help`, focused pose/render tests, and the offline overnight smoke pass; CUDA-only commands fail with a precise capability message.
8. No historic PR or `origin/dev` commit is merged wholesale; each salvaged change is a small, current-main-based commit with independent tests.

## Verification sequence

1. Provider unit tests: build/import, eligibility, strict forced modes, counters, point/face distance, rasterization, hostile inputs.
2. ARIA unit tests: device resolution, preflight/provenance, pose geometry, camera conversion, depth renderer.
3. Integration tests: candidate generation/render/RRI with fixed fixtures on CPU, Mojo, and CUDA where available.
4. Cross-host E2E: minimal VIN store and horizon-2 rollout with artifact comparison and exact identity checks.
5. Static checks: `uv lock --check`, Ruff, mypy, and an invariant grep for distributed backend policy.
6. Operational smoke: fresh Mac bootstrap, fresh Ubuntu bootstrap, CLI help, offline overnight run, interrupted-run resume.

## Risks and controls

- **Fork maintenance:** pin immutable SHAs, keep a narrow patch series, test against the selected upstream revision, and document ownership.
- **Numerical divergence:** fixed digests, non-tied fixtures, separate tie reporting, field-specific tolerances, and reference CPU runs.
- **Silent fallback:** forced-mode failures plus per-operator counters and artifact provenance.
- **MPS unsupported operations:** keep geometry explicitly on CPU/Mojo and allow MPS only at measured model boundaries; never claim zero-copy interop.
- **Mac throughput:** bound workloads and reserve production generation/training for CUDA.
- **Dependency/lock drift:** platform markers or separate lock inputs, exact Torch/provider/Mojo pins, clean-cache CI smokes.
- **Historic diff contamination:** reconstruct small commits on current main; do not cherry-pick merge commits, vendored skills, generated state, or obsolete scaffold files.

## Recommended first implementation slice

Create two reviewable PRs:

1. **PyTorch3D provider PR:** rebase and minimize the `f131395` fork, retain direct Mojo operators and strict/observable dispatch, and publish clean-build plus parity evidence.
2. **ARIA integration PR:** platform-select the immutable provider, add the one geometry-device resolver and provenance surface, and port focused equivalence/E2E tests. CUDA remains the unchanged default.

Do not begin with the broader `origin/dev` backend. Mine it only after the provider PR establishes the seam and its parity tests identify a concrete missing capability.
