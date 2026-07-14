# Test strategy: PR 23 Apple-Silicon Mojo

- Status: draft pending Ralplan consensus
- Reference implementation: PyTorch3D C++ CPU at `b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881`
- Required runtime: Apple arm64, Python 3.11, Torch 2.4.1, Mojo 1.0.0b2

## Proof levels

### 1. Build and provenance

- Fresh uv environment builds the fork against runtime Torch, then imports `_C` in two processes.
- `file` proves arm64 artifacts; `otool -L` proves expected Torch libraries and no CUDA/x86 dependency.
- Mojo reports the effective Apple arm64 host target.
- A direct `PythonModuleBuilder` Mojo extension is compiled under `build_lib`, wheeled, installed with the exact Mojo runtime package, and called successfully without any operator C++/header bridge. Mach-O inspection proves arm64, macOS 11.0 minimum, a stable `@rpath` install name, and only relative runtime lookup.
- `PYTORCH3D_REQUIRE_MOJO=1` passes only when the compiled Mojo capability executes; it must fail loudly when Mojo is unavailable or inputs are unsupported. Per-operator counters prove point-face, face-point, raster, and any CPU-coarse/Mojo-fine execution separately.

### 2. Point/face numeric parity

Compare public PyTorch3D wrappers with Mojo disabled versus required:

- one point inside, outside, on edge, and on vertex;
- degenerate triangles below/above `min_triangle_area`;
- multiple packed batches and unequal point/face counts;
- empty tensors and boundary offsets matching upstream behavior;
- equal-distance ties, including exact selected index;
- noncontiguous inputs, wrong ranks/dtypes/devices, invalid or nonmonotonic offsets, and `requires_grad` rejection or fallback, with upstream validation order preserved;
- deterministic holdout random meshes across small and medium sizes.

Assert exact shapes, dtypes, devices, indices, and masks. Use exact equality for indices and agreed float tolerance at most `rtol=1e-4, atol=1e-4` unless the reference demonstrates a tighter safe bound.

### 3. Raster numeric parity

Compare `MeshRasterizer` outputs with Mojo disabled versus required for the supported profile:

- single triangle, occluding triangles, empty background, and depth ties;
- batched meshes and non-square images;
- zero-area and behind-camera faces;
- a face crossing `znear` that is clipped into two neighbors, including suppression, exact original-face index conversion, depth, and barycentric reconstruction;
- culling on/off as used by ARIA;
- perspective correction and barycentric clipping values used by ARIA;
- small randomized projected meshes held out from implementation.

Assert exact `pix_to_face` and background masks; compare z-buffer, barycentric coordinates, and distances within tolerance. Unsupported blur, `faces_per_pixel>1`, dtype, or autograd cases must take an explicit tested fallback or raise under required-Mojo mode.

### 4. ARIA integration

- Pose candidate clearance test uses the real public point-face function, not a mock.
- RRI tests cover both point-to-face and face-to-point numeric outputs.
- Candidate depth rendering returns the existing `(depth, pix_to_face)` contract and unprojects consistently.
- Dependency metadata resolves the immutable fork SHA and build/runtime Torch versions match.
- Search proves there are no ARIA-local `.mojo` geometry implementations.

### 5. End-to-end generation

Under `PYTORCH3D_REQUIRE_MOJO=1`:

- Build a tiny VIN store, reopen it, validate Zarr arrays, `sample_index.jsonl`, splits, shapes, finite values, and one collated model-ready sample.
- Build a seeded rollout with at least two decisions, reopen it, validate replay continuity, pose validity, rendered depth, target RRI, and deterministic metadata.
- Prefer the smallest available real scene. Run the same CLI paths on deterministic synthetic fixtures as permanent regression tests.
- Interrupt one write and verify atomic recovery/no corrupt success marker when supported by existing store semantics.

### 6. Performance and LOC

- Warm up separately from timing; record median and p95 over repeated trials.
- Compare upstream C++ CPU versus Mojo on identical inputs for point-face, face-point, raster, pose pruning, and two-step rollout.
- Include cold compile/import separately from steady-state runtime.
- Record machine, process/thread settings, dimensions, faces, points, pixels, and commit SHA. Targets are 1.25× lower point/face median and 1.20× lower raster median. Hard gates are parity, explicit Mojo provenance, p95/end-to-end no worse than the fastest retained native alternative, and a recorded three-attempt plateau when a target is not reached.
- Track implementation-only added/deleted LOC per iteration. Reject an optimization when it regresses parity, representative runtime, robustness, or necessary LOC without compensating rubric value.

### 7. Repository verification

PyTorch3D fork:

```text
python -m unittest <new CPU/Mojo-specific point-mesh suite>
python -m unittest <new CPU/Mojo-specific raster suite>
dev/linter.sh
```

The existing upstream point-mesh/raster modules currently select CUDA unconditionally on this CPU-only wheel and are not Mac acceptance gates. Run their CPU-addressable test methods explicitly where useful; reserve full upstream discovery for the Linux/CUDA regression environment or after upstream tests have correct capability skips.

ARIA-NBV:

```text
uv run --project aria_nbv pytest <targeted suites>
uv run --project aria_nbv pytest
make check-agent-memory
```

Run the smallest targeted checks after each edit, broader suites at story boundaries, then code review and UltraQA at the final gate.

## Named real-data fixture

- Primary: scene `81286`, sample `ASE_81286_Atek_000002`, mesh `scene_ply_81286.ply`, EVL checkpoint `model_lite.pth`, acquired by the exact rsync commands in the PRD from `ubuntu:~/repos/ARIA_NBV`.
- Official fallback: EFM3D ASE eval scene `81022` and `model_lite.pth`, acquired through the documented Project Aria manifests/zip and EFM3D one-sequence command.
- Current external evidence: GitHub LFS reports repository budget exhausted; SSH times out during banner exchange; official manifests require email access. Synthetic evidence never substitutes for this gate.
