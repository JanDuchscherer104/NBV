# Deep-interview specification: PR 23 Apple-Silicon Mojo

- Recorded: 2026-07-13T22:29:41Z
- Status: complete
- Source: explicit user requirements plus verified repository and host evidence
- Handoff: `$ralplan`

## Outcome

Make ARIA-NBV pull request 23 run natively on Apple Silicon for VIN-store generation, multi-step rollout dataset generation, mesh rendering, and pose generation. Geometry kernels required by those paths are implemented in a maintained PyTorch3D fork, colocated with the corresponding CPU/CUDA implementations and exposed through stable PyTorch3D interfaces. ARIA-NBV consumes a pinned fork commit and does not own duplicate Mojo kernels.

## Binding constraints

1. Native arm64 execution on this Mac; no Rosetta and no CUDA runtime on the Mac path.
2. Mojo owns the accelerated geometry implementations. PyTorch remains the public tensor/API boundary.
3. Mojo implementation sources live in `JanDuchscherer104/pytorch3d`, parallel to PyTorch3D's CPU/CUDA operator sources.
4. Preserve PyTorch3D and ARIA contracts: tensor shapes, dtypes, masks, ordering, ranking, coordinate frames, empty-input behavior, and deterministic seeded behavior.
5. Prefer deletion and narrow dispatch seams over new abstractions or dependencies.
6. Iterate with measured correctness, runtime, and necessary implementation LOC. Keep only changes that improve the rubric without regressions.
7. Continue through code review, hostile QA, and professor/critic autoresearch until the user interrupts or the complete rubric is independently approved.

## Verified starting state

- Host: native arm64 Apple Silicon, macOS 26.4.1.
- ARIA worktree: `/Users/jd/Documents/Aria-NBV/macos-pr23`, branch `codex/pr23-apple-silicon`, PR head `2b5095e`.
- PyTorch3D fork worktree: `/Users/jd/Documents/Aria-NBV/pytorch3d-mojo`, branch `codex/mojo-apple-silicon-ops`, base `b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881`.
- ARIA environment resolves Torch 2.4.1 and PyTorch3D 0.7.9, but `import pytorch3d._C` deterministically fails because the extension references `c10::impl::getGlobalPyInterpreter()` absent from the runtime `libc10.dylib`.
- Mojo is not yet installed. Full Xcode/Metal command-line compilation is unavailable; native Mojo CPU execution remains viable and is the first implementation target.

## Pressure-tested decisions

### Ownership seam

Rejected: repo-local ARIA Mojo modules with ARIA-specific adapters. This duplicates PyTorch3D geometry ownership and violates the user override.

Selected: PyTorch3D operator packages own Mojo sources and dispatch. ARIA sees existing PyTorch3D APIs plus the smallest explicit backend configuration needed for rollout generation.

### First vertical slice

Start with packed point-to-face distance because it is shared by pose collision filtering and RRI, has a compact forward-only inference contract, and can prove fork packaging, Mojo import, PyTorch tensor conversion, parity, and ARIA consumption before rasterization is attempted.

Then implement mesh rasterization through the same fork-owned pattern. Complete VIN-store and rollout generation only after both geometry primitives pass isolated parity tests.

### CPU versus Metal

Native Mojo CPU is the required baseline and does not depend on an undocumented PyTorch-MPS/Metal zero-copy bridge. Metal is an optimization lane only when the installed Xcode/Metal toolchain and measurements justify it. "Native Apple Silicon" does not permit an x86 or CUDA fallback.

### Backend behavior

Automatic fallback may preserve portability, but verification must expose which implementation executed. A test cannot count as Mojo coverage if it silently used the existing C++ CPU kernel.

### Direct Mojo boundary refinement

After the initial link spike, the selected implementation was tightened to a genuine Mojo Python extension built with `PythonModuleBuilder`. PyTorch3D's public Python functions dispatch directly to `pytorch3d._mojo`; no new operator `.cpp` or `.h` bridge is allowed. The upstream `_C` extension remains only the reference, autograd, and unsupported-input fallback. The direct module matched the bridge's call cost and removed the bridge code, so this is both the clearest interpretation of Mojo ownership and the lower-LOC design.

## Non-goals

- Rewriting model training or unrelated EFM3D operations in Mojo.
- Changing rollout semantics, coordinate conventions, or dataset schemas.
- Replacing PyTorch3D's CUDA path on Linux.
- Shipping a second ARIA-specific geometry API.
- Adding Metal-specific complexity before a reproducible CPU baseline and benchmark exist.

## Acceptance criteria

1. The fork builds and imports against the exact ARIA runtime Torch on arm64.
2. Fork tests prove Mojo point-mesh and rasterization parity against PyTorch3D references, including edge cases used by ARIA.
3. ARIA pins an immutable fork commit and contains no duplicate Mojo kernels for these operators.
4. Pose generation, rendering, VIN-store generation, and a multi-step rollout dataset smoke complete natively with explicit Mojo execution evidence.
5. Targeted tests, lint/static checks, code review, and hostile QA pass.
6. Benchmarks and LOC accounting are recorded; only rubric-positive iterations remain.
7. Independent professor/critic review returns APPROVE and architecture review returns CLEAR.

## Ambiguity ledger

- Real dataset availability is not yet verified. Synthetic contract-level fixtures are acceptable for early vertical slices; final end-to-end evidence should use the smallest available real sample when repository data is present.
- Direct MPS tensor interop with Mojo is not assumed because no supported zero-copy contract has been found. The fork must make host transfers explicit if MPS callers are supported.
- Remote `ssh ubuntu` is currently unreachable during SSH banner exchange. This does not block Mac implementation; remote parity is deferred until connectivity returns.
