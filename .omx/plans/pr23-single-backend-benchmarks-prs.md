# PR 23: one backend seam, equivalence report, and two-PR delivery

## Requirements summary

- Keep genuine Mojo implementations in the PyTorch3D fork, beside the existing CPU/CUDA implementations. Do not add an operator C++ bridge or headers.
- Keep ARIA-NBV changes surgical: rendering, pose generation, RRI, VIN generation, and rollout generation continue to call public PyTorch3D interfaces.
- Replace the two experimental Mojo environment flags with one global interface: `PYTORCH3D_BACKEND=auto|cuda|mojo|cpu`.
- Run matched numerical-equivalence and runtime experiments for point-to-face, face-to-point, rasterization, VIN-store generation, and horizon-2 rollout generation.
- Publish a compact, reproducible HTML report through a new Quarto Resources page covering architecture, setup, usage, supported contracts, limitations, correctness, timings, and raw evidence.
- Independently review, adversarially test, push, and open PRs for both repositories.

## Architecture decision

PyTorch3D is the deep module. Its existing public operations are the interface and test surface. The backend seam is the private dispatch in `pytorch3d/_mojo_ops.py`; upstream CPU, upstream CUDA, and native Mojo are adapters at that seam. ARIA's existing `BaseConfig._resolve_device` function is the only ARIA integration point for the same global backend value.

```text
PYTORCH3D_BACKEND
       |
       +-- ARIA BaseConfig device seam
       |       +-- pose / render / RRI / VIN / rollout configs
       |
       +-- PyTorch3D operator seam
               +-- upstream CUDA adapter
               +-- native Mojo adapter
               +-- upstream CPU reference adapter
```

The deletion test favors this design: deleting the two seam changes would force backend selection back into every data-generation config and operator call. Adding an ARIA geometry abstraction would instead be a shallow middle layer over PyTorch3D and is rejected.

### Interface contract

- `auto`: CUDA tensors use upstream `_C`; eligible CPU tensors use Mojo when installed; other inputs use upstream CPU.
- `cuda`: ARIA resolves validated devices to CUDA; PyTorch3D requires CUDA tensors and CUDA availability, failing instead of falling back.
- `mojo`: ARIA resolves validated devices to CPU; PyTorch3D requires the supported CPU/no-grad Mojo contract, failing instead of falling back.
- `cpu`: ARIA resolves validated devices to CPU; PyTorch3D bypasses Mojo and requires CPU tensors.
- Unknown values fail with the allowed values. The selected backend is read at call/validation time so tests and CLI processes do not require import-order tricks.

## Acceptance criteria

1. `pytorch3d/_mojo_ops.py` contains the only operator dispatch policy; the old `PYTORCH3D_DISABLE_MOJO` and `PYTORCH3D_REQUIRE_MOJO` interfaces no longer exist.
2. `aria_nbv/utils/base_config.py::_resolve_device` honors the same global backend value, while renderer, pose, RRI, VIN, and rollout product call sites gain no backend branches.
3. `PYTORCH3D_BACKEND=mojo` proves nonzero Mojo counters for point-to-face, face-to-point, and rasterization during native VIN and horizon-2 rollout runs on Apple arm64.
4. `PYTORCH3D_BACKEND=cuda` exercises all three upstream CUDA forwards and the same VIN/rollout schemas on the RTX 3080 Ti host.
5. Fixed non-tied fixtures use the same fixture digest and PyTorch3D SHA on both hosts. Integer outputs, schemas, shapes, masks, lineage, and selected rows are exact; float differences are reported with mismatch count, max absolute error, and max relative error under `rtol=2e-5, atol=2e-6` unless a stricter existing field contract applies.
6. Tie cases are reported separately. A fixture or PyTorch3D SHA mismatch aborts aggregation rather than producing a comparison.
7. Timings use warmups, raw trials, `perf_counter_ns`, explicit CUDA synchronization, fixed/recorded Torch thread count, and median/p5/p95/IQR. Same-host CPU-to-Mojo and CPU-to-CUDA speedups are allowed; cross-host CUDA/Mojo observations are absolute and hardware-labeled with no direct ratio.
8. The Quarto site contains a Resources entry for the new page, renders without errors, and embeds the compact report with links to raw machine-readable evidence.
9. A fresh locked Mac install builds/imports arm64 `_mojo.so`; focused fork tests, ARIA targeted tests, VIN E2E, rollout E2E, lint, lock validation, code review, UltraQA, and architecture-invariant review are green.
10. Both GitHub PRs are open, cross-linked, and describe exact setup, backend usage, supported contracts, numerical results, timings, hardware, residual limitations, and test evidence.

## Implementation steps

1. Restore and pin the scientifically equivalent raster formulation in `pytorch3d/csrc/rasterize_meshes/rasterize_meshes_mojo.mojo:105-123`; reject the faster formulation in the experiment ledger because it changes normalized rollout targets.
2. Deepen the backend seam in `pytorch3d/_mojo_ops.py:23-70,129-189`: parse one backend value, enforce device/capability requirements, and preserve auto fallback. Update fork tests in `tests/test_point_mesh_mojo.py` and `tests/test_rasterize_meshes_mojo.py` at their current environment-control helpers.
3. Make the smallest ARIA integration in `aria_nbv/aria_nbv/utils/base_config.py:112-118`; reuse the same value to resolve validated device fields. Update only tests that intentionally select a backend. Do not edit `rri_metrics/point_mesh.py:44`, `pose_generation/geometry.py:10`, or `rendering/pytorch3d_depth_renderer.py:153` to add dispatch logic.
4. Add one focused cross-platform benchmark/equivalence runner in the PyTorch3D fork for the three exact supported forward contracts. Emit raw JSON plus a stable fixture bundle/digest and record repository SHA, dirty state, hardware, software, shapes, settings, synchronization, warmups, and trials.
5. Build the exact fork SHA on Apple arm64 and Ubuntu CUDA. Run the shared operator fixtures on Mac CPU/Mojo and Ubuntu CPU/CUDA. Transfer only fixture/evidence artifacts between hosts and aggregate only after digest/SHA validation.
6. Sync the named real ASE fixture from `~/repos/ARIA-NBV` on Ubuntu. Run native Apple VIN and horizon-2 rollout generation under `mojo`; run matched Ubuntu generation under `cuda`; compare stores field-by-field and record timing/counter evidence. Keep synthetic fixtures labeled as regression-only.
7. Generate a compact standalone report at `docs/figures/benchmarks/pytorch3d-backends/report.html` with raw evidence beside it. Add `docs/contents/mojo_pytorch3d.qmd`, register it in both Resources navigation locations in `docs/_quarto.yml:75,124`, and correct the stale CPU-only warning in `docs/contents/setup.qmd:80-90`.
8. Run a behavior-locked cleanup pass over changed implementation files only, preferring deletion and preserving the one-seam invariant. Re-run all verification after cleanup.
9. Review both diffs independently along Standards and Spec axes, plus separate code-reviewer and architect gates. Resolve findings and rerun affected evidence.
10. Run UltraQA with normal and hostile backend values, absent Mojo/CUDA, wrong device, noncontiguous/grad inputs, degeneracy/ties, unsupported raster settings, interrupted generation, dirty worktrees, stale partial stores, retries, reproducibility, misleading output, and cleanup checks.
11. Push immutable branch heads and open cross-linked PRs for `JanDuchscherer104/pytorch3d` and `JanDuchscherer104/ARIA-NBV`. Complete the durable goal only after both PRs and the professor/critic gate are clean.

## Risks and mitigations

- **Cross-machine timing confound:** never compute a CUDA/Mojo ratio across the M5 Max and RTX 3080 Ti; present same-host reference speedups plus absolute hardware-qualified observations.
- **CUDA reduction ties:** isolate tied fixtures and judge distances separately from an equally valid tied index; use non-tied fixtures for exact cross-adapter indices.
- **Global override surprises:** invalid or unavailable forced backends fail early; `auto` retains current production behavior.
- **Unsupported Mojo contracts:** forced `mojo` fails with the violated contract; `auto` retains upstream fallback.
- **ARIA scope growth:** reject per-call-site branches and new geometry wrappers; the product-code target is one central device resolver plus dependency pinning.
- **Real-data cost:** use the established one-sample/one-target/horizon-2 profiles first, with bounded commands and explicit partial-store cleanup.
- **Generated report drift:** report generation validates fixture/SHA identity and links raw JSON; Quarto embeds the generated artifact rather than duplicating numbers by hand.

## Verification commands and evidence

- Fork: build arm64/CUDA extensions; run focused Mojo/backend tests; run shared operator fixture/equivalence runner on both hosts; inspect Mach-O/CUDA linkage.
- ARIA: `uv lock --check`, targeted config/pose/render/RRI/VIN/rollout tests under forced backends, Ruff, strict real-data VIN and rollout commands, field-by-field store comparison, and Quarto render.
- Review: parallel Standards and Spec subagents per repository, followed by independent code-reviewer `APPROVE` and architect `CLEAR` evidence.
- QA: required UltraQA scenario matrix and cleaned temporary harnesses/artifacts.
- Delivery: verify both remote branch SHAs and both GitHub PR URLs after creation.

## Durable execution staffing

- Leader: Ultragoal ledger ownership, integration, final verification, and PR publication.
- Bounded explore/executor lanes: backend seam mapping, benchmark/report implementation, and CUDA-host execution where independent.
- Independent review lanes: Standards, Spec, code-reviewer, architect, and final professor/critic. Reviewers do not author the code they approve.
