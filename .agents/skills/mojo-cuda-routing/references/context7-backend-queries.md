# Context7 Backend Queries

Use this reference only when ARIA-NBV backend work depends on current external library behavior. The repo-local source, installed packages, and focused tests remain the authority for ARIA-owned interfaces.

## Tool Route

- Use the resolve and query tools named by the repo-local
  `aria-nbv-context` Context7 registry.
- Reuse the exact library IDs owned by that registry; do not copy them into this
  reference.
- Pair external answers with local evidence: installed version, lockfile/source commit, and the ARIA call site or test affected.

## Query Sequences

Mojo and Modular:

- Select the Mojo library entry from the central registry.
- Query `Python interop, importable Mojo modules, package layout, ownership, FFI, and GPU kernels for Python-callable kernels`.
- Query `Apple Silicon support, device selection, execution targets, and limitations relevant to PyTorch tensor interop`.

PyTorch:

- Select the PyTorch library entry from the central registry.
- Query `device semantics for cpu cuda mps, tensor movement, dtype support, serialization map_location, and deterministic comparisons`.
- Query `C++ extension build behavior, ABI compatibility, build isolation, and platform markers for installed Torch 2.4.x style environments`.

PyTorch3D:

- Select the PyTorch3D library entry from the central registry.
- Query `Meshes, PerspectiveCameras, MeshRasterizer, RasterizationSettings, Fragments zbuf pix_to_face, and camera coordinate conventions`.
- Query `point_face_distance, point-mesh distance primitives, extension availability, CUDA requirements, and CPU fallback behavior`.

uv packaging:

- Select the uv library entry from the central registry.
- Query `PEP 508 platform markers, direct git dependencies, lockfile resolution across macOS and Linux, dependency groups, and extra-build-dependencies`.
- Query `build isolation, editable local sources, workspace sync, and per-platform wheel/source selection`.

ARIA-adjacent libraries:

- EFM3D: query `CameraTW PoseTW tensor wrappers, camera frames, and device movement`.
- ATEK: query `ASE snippet schema and mesh/calibration fields`.
- Project Aria tools: query `camera calibration, pose transforms, coordinate frames, and VRS access`.

## Required Evidence

For backend-sensitive changes, include these facts in the implementation note, PR body, or generated provenance:

- Mac lane: OS/architecture, Torch version, provider repository, provider commit, selected device, and PyTorch3D import/rasterizer smoke result.
- Ubuntu lane: GPU name, CUDA availability, Torch version, upstream PyTorch3D commit, and CUDA rasterizer preflight result.
- Real-data parity: dataset scene/snippet or rollout manifest used, command line, artifact path, and the exact invariant or tolerance checked.
