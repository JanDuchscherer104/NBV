# Ralplan PRD: PR 23 native Apple-Silicon data generation

- Drafted: 2026-07-13
- Consensus status: pending sequential architect then critic review
- Overall owner: Autoresearch goal `pr23-apple-silicon-mojo`
- Implementation repositories:
  - `/Users/jd/Documents/Aria-NBV/pytorch3d-mojo`
  - `/Users/jd/Documents/Aria-NBV/macos-pr23`

## Objective

Deliver a minimal, reproducible Apple-arm64 path for ARIA-NBV PR 23 that completes pose generation, depth rendering, RRI, VIN-store generation, and multi-step rollout dataset generation. The three critical native operator families—point-to-face forward, face-to-point forward, and rasterize-meshes forward—must execute Mojo implementations owned by the PyTorch3D fork through PyTorch3D's existing interfaces.

## Architecture decision

PyTorch3D is the deep module. Its existing Python functions remain the public seam. On eligible Apple-arm64 inputs they call a private `pytorch3d._mojo` Python extension built directly from Mojo with `PythonModuleBuilder`; `_C` remains the upstream reference, autograd, and unsupported-input fallback. No new operator `.cpp` or `.h` bridge is permitted. ARIA owns dependency selection and portable runtime configuration only.

The retained build boundary compiles `_mojo.mojo` directly to an arm64 Python shared library, gives it a relative `@loader_path` lookup for the exact Mojo runtime package, wheels it beside `_C`, and verifies import/call behavior plus every Mach-O dependency in a clean environment. The earlier Mojo-object/C++-bridge spike was useful evidence but was deleted because the direct Mojo extension has the same measured call cost with less code and clearer ownership.

### Capability profile

Mojo dispatch is forward-only and initially limited to the contracts used by data generation:

- CPU-contiguous float32 geometry tensors and contiguous int64 offsets/counts; exact ranks and monotonic packed-batch offsets are validated in upstream order.
- Point/face packed-batch distance with PyTorch3D tie and degeneracy behavior.
- Rasterization with `faces_per_pixel=1`, `blur_radius=0`, `bin_size=0`, forward-only, perspective correction enabled, barycentric clipping disabled, backface culling disabled, and `z_clip_value=znear` preprocessing including clipped-neighbor mapping.
- Unsupported dtype, autograd-sensitive, blur, multi-hit, or non-CPU storage remains on upstream CPU/CUDA.

`PYTORCH3D_REQUIRE_MOJO=1` converts any silent fallback on a required Apple path into an error. Private per-operator counters for point-face, face-point, naive raster, and any coarse-plus-fine raster path make execution provenance testable without changing public operator signatures. Eligibility covers build capability, device, dtype, contiguity, ranks, offsets/counts, `requires_grad`, and the complete raster option set while preserving upstream validation/error order.

## Work packages

### G0 — Reproducible arm64 build and baseline

1. Install stable Mojo 1.0.0b2 into a Python 3.11 development environment and record effective arm64 target.
2. Build a trivial direct Mojo Python extension and clean-runtime wheel before geometry code. `PYTORCH3D_BUILD_MOJO` is active only for Darwin arm64; explicit required-build mode fails rather than silently omitting Mojo.
3. Make the PyTorch3D fork build against the exact installed Torch 2.4.1 ABI.
4. Fix the current `getGlobalPyInterpreter` failure with uv build dependency `match-runtime=true` when supported, otherwise exact Torch 2.4.1 dependency metadata; invalidate only the affected PyTorch3D artifact.
5. Gate `-Wno-invalid-specialization` narrowly to Darwin/Apple Clang where Torch 2.4.1 meets libc++'s non-specializable type-trait annotation. A minimal local probe already proves that exact flag and a correct-ABI build; do not upgrade Torch as a shortcut.
6. Record baseline C++ CPU correctness/runtime for point-mesh and restricted rasterization.
7. Verify `_C` and Mojo artifacts are arm64 and contain no CUDA runtime dependency.

Exit: a clean source build imports in a fresh Python 3.11 environment twice, and the ABI root cause has a regression test or deterministic build assertion.

### G1 — Fork-owned Mojo point/face distance

1. Add `pytorch3d/csrc/point_mesh/point_mesh_mojo.mojo` beside the operator's CPU/CUDA files, imported by the fork's direct Mojo Python module.
2. Validate packed tensor contracts and allocate Torch outputs in the Mojo Python binding; keep eligibility/provenance and `_C` fallback in one small Python module.
3. Preserve squared-distance math, minimum triangle area behavior, packed-batch offsets, and last-index-on-tie behavior.
4. Route both `point_face_dist_forward` and `face_point_dist_forward` through the same narrow implementation shape to avoid duplicate math.
5. Add forced-reference and required-Mojo modes strictly for deterministic verification.

Exit: public `point_face_distance` and `face_point_distance` match upstream CPU references on fixed and holdout randomized cases; required-Mojo mode proves dispatch. Pose pruning and RRI targeted tests pass.

### G2 — Fork-owned Mojo hard-depth rasterization

1. Add `pytorch3d/csrc/rasterize_meshes/rasterize_meshes_mojo.mojo` beside the operator's CPU/CUDA files. Preserve PyTorch3D's four-output contract and the original-face conversion after near-plane clipping.
2. Dispatch from the existing Python rasterization wrapper to the direct Mojo module when the capability profile matches.
3. Parallelize independent pixels in Mojo; validate and allocate Torch outputs in its Python binding.
4. Benchmark naive Mojo against upstream CPU.
5. Include a partially near-plane-clipped face that becomes two triangles, with exact clipped-neighbor suppression and original-face mapping, in the parity gate.
6. If representative dense-mesh runtime is not viable, reuse PyTorch3D's existing coarse CPU bins and implement only the currently missing fine CPU stage in Mojo. Count that explicit CPU-coarse/Mojo-fine combination separately in provenance. Change ARIA's `bin_size` only when measurements prove the binned path.

Exit: `MeshRasterizer` parity passes for ARIA settings, required-Mojo mode proves execution, and the representative benchmark is no slower than the retained alternative. Unsupported settings deterministically use or reject fallback according to policy.

### G3 — Minimal ARIA integration

1. Push an immutable fork commit only after fork tests pass; pin ARIA to its full SHA and refresh `uv.lock`.
2. Express PyTorch3D's build-time Torch as `match-runtime`/exact ABI rather than an unconstrained isolated dependency.
3. Add a reproducible Apple-native environment command/profile using Python 3.11 and CPU geometry. Do not introduce an undocumented MPS-to-Mojo bridge.
4. Replace CUDA-only rollout smoke configuration with native-safe values while retaining Linux CUDA profiles.
5. Remove the pose CUDA retry and stale GPU-only documentation only after fork parity makes them redundant.
6. Keep camera transforms and unprojection in existing Torch/PyTorch3D code; they are not native custom-kernel blockers.

Exit: ARIA imports the pinned fork from a clean uv sync, contains no Mojo kernel duplicate, and targeted pose/render/RRI tests pass with `PYTORCH3D_REQUIRE_MOJO=1`.

### G4 — Data and end-to-end generation

1. Use the exact primary real-data fixture already established by this project: scene `81286`, sample `ASE_81286_Atek_000002`, `.data/ase_meshes/scene_ply_81286.ply`, and `.logs/ckpts/model_lite.pth`. Acquire it from the user-designated main repo when SSH recovers:

   ```text
   rsync -a ubuntu:~/repos/ARIA_NBV/.data/ase_efm/81286/ .data/ase_efm/81286/
   rsync -a ubuntu:~/repos/ARIA_NBV/.data/ase_meshes/scene_ply_81286.ply .data/ase_meshes/
   rsync -a ubuntu:~/repos/ARIA_NBV/.logs/ckpts/model_lite.pth .logs/ckpts/
   ```

   Official fallback is EFM3D's documented ASE eval scene `81022` plus `model_lite.pth`: obtain `AriaSyntheticEnvironment_ATEK_download_urls.json`, `ase_mesh_download_urls.json`, and `evl_model_ckpt.zip` from the Project Aria EFM3D/ASE pages; run `external/efm3d/prepare_inference.sh`, then the documented one-sequence `dataverse_url_parser.py --config-name efm_eval ... --max-num-sequences 1` and mesh downloader. These manifests are email-access-gated, not credential-free public files.
2. Run the smallest real VIN offline-store build. Validate Zarr schema, sample index, split files, and at least one model-ready sample.
3. Run a deterministic rollout of at least two steps. Validate replay rows, rendered depths, candidate poses, target RRI, and persisted dataset reopening.
4. If real assets are unavailable, preserve a fully synthetic CLI-level fixture as regression coverage but do not treat it as completion. Record an explicit `external_data_blocked` state only after three independent acquisition attempts confirm the same blocker (currently GitHub LFS budget exhaustion plus SSH banner timeout and email-gated official manifests). Continue all other implementation, parity, QA, and performance work; recheck acquisition at story boundaries.
5. Retry SSH Ubuntu connectivity and run Linux/CUDA regression tests when reachable; Mac completion does not depend on remote availability.

Exit: native real-data smokes pass, or the only remaining gap is externally inaccessible data documented with successful synthetic end-to-end evidence and all safe retrieval alternatives exhausted.

### G5 — Simplification and performance autoresearch

1. Record implementation-only LOC separately for fork build glue, Python dispatch, and Mojo bindings/kernels; tests and generated lockfiles are separate.
2. Benchmark cold build/import, warm point/face distance, naive raster, binned raster when present, pose candidate pruning, and a two-step rollout.
3. Iterate one hypothesis at a time. Keep changes only when parity remains green and they improve runtime, necessary LOC, or robustness.
4. Prefer fused shared geometry math, deletion of pass-through adapters, preallocated output, contiguous traversal, pixel parallelism, and coarse-bin reuse.
5. Run a final code-simplifier pass over only modified implementation code.

Optimization targets on fixed representative fixtures are 1.25× lower median steady-state time for point/face distance and 1.20× for rasterization versus upstream C++ CPU. Completion gates are parity, no end-to-end regression versus the fastest retained native alternative, explicit provenance, and retention of only rubric-positive iterations. After three distinct profiler-backed, parity-safe attempts fail to improve a kernel's median runtime, p95, necessary LOC, or robustness, record the plateau, retain the best implementation, and move to the next rubric item rather than deadlocking the goal. Keep new non-test implementation below 1,200 LOC initially and pressure it downward after correctness.

### G6 — Autopilot review gates

1. Run independent Standards and Spec code reviews for both repositories.
2. Resolve all P0/P1 and any evidence-backed P2 findings; re-run changed tests.
3. Run UltraQA hostile scenarios, including absent Mojo, wrong Torch ABI, noncontiguous input, empty batches, degenerate/tied faces, unsupported raster settings, interrupted store writes, and dataset reopen.
4. Execute the professor/critic autoresearch rubric. Continue on REVISE; stop only at APPROVE plus architecture CLEAR or user interruption.

## Ultragoal decomposition

The existing Autoresearch Codex goal remains the authoritative objective. Strict Ultragoal goal creation/checkpoint reconciliation cannot legally coexist with that different active objective, so the App-safe Ultragoal adaptation is an artifact-backed story ledger under the same aggregate mission; it must not call `create_goal`, replace, or falsely checkpoint the active objective. This limitation is recorded explicitly while preserving Ultragoal's decomposition and evidence discipline:

1. `build-arm64-abi`
2. `point-mesh-mojo`
3. `raster-mojo`
4. `aria-fork-integration`
5. `vin-store-native-e2e`
6. `rollout-native-e2e`
7. `simplify-benchmark-review`

Stories execute sequentially where their evidence depends on an earlier artifact; isolated documentation, asset discovery, and verification may use bounded native subagents.

## Risks and predefined responses

- **Direct Mojo import fails:** keep the fork-owned Python extension and relative `@loader_path` runtime lookup; do not add a C++ bridge or switch to ARIA-owned kernels.
- **Torch ABI mismatch recurs:** make isolated build match runtime, clear only PyTorch3D cache, and prove in a fresh environment.
- **Raster parity surface grows:** keep the capability profile restricted and fall back for unsupported general PyTorch3D settings.
- **Naive raster is too slow:** implement Mojo fine rasterization over existing coarse bins before attempting Metal.
- **MPS integration is requested by a dependency:** make CPU transfer explicit or keep the affected pipeline CPU; do not claim zero-copy Metal interop.
- **Full Xcode remains absent:** continue native Mojo CPU work. Metal claims remain out of scope until toolchain evidence exists.
- **Real data absent:** install Git LFS and fetch public assets; keep synthetic CLI evidence but do not relabel it real-data validation.
- **License provenance:** write fork kernels cleanly from PyTorch3D contracts/reference math and retain applicable notices; do not copy historical ARIA donor wholesale.

## Definition of done

All autoresearch rubric items pass; both worktrees are reviewable and clean except deliberate artifacts; fork and ARIA commits are immutable/pinned; fresh arm64 setup reproduces; required-Mojo VIN-store and two-step rollout evidence exists; tests/reviews/QA are green; benchmark and LOC ledgers show only positive retained iterations; professor says APPROVE and architect says CLEAR.
