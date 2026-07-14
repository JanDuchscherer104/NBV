# PyTorch3D macOS ABI diagnosis

## Symptom

`import pytorch3d._C` fails against ARIA's runtime Torch 2.4.1 because the extension references `c10::impl::getGlobalPyInterpreter()`, which the runtime `libc10.dylib` does not export.

## Ranked hypotheses and results

1. **Isolated build used a newer Torch — confirmed.** ARIA's uv build override declares unconstrained `torch`. On Python 3.11, the same resolver selects Torch 2.13.0. Clearing only the PyTorch3D uv cache and rebuilding repeats the mismatched symbol failure.
2. **Stale wheel cache — rejected.** A no-cache rebuild reproduces the identical binary failure.
3. **PyTorch3D commit incompatible with runtime Torch — rejected at ABI level.** Building the exact fork commit with build isolation disabled uses the runtime Torch 2.4.1 headers. With the Clang-26 compatibility diagnostic suppressed, the extension imports successfully in two fresh processes and executes point/face distance plus rasterization.
4. **Deployment target/link path — rejected for the observed import failure.** The correctly rebuilt arm64 extension links and loads the same runtime Torch dylibs.

## Secondary toolchain incompatibility

Current Apple Clang/libc++ 26 marks standard type traits as non-specializable. Torch 2.4.1's bundled `c10/util/strong_type.h` specializes `std::is_arithmetic`, so a correct-ABI source build fails with `-Winvalid-specialization`.

A minimal translation unit including `torch/extension.h` fails without and succeeds with exactly `-Wno-invalid-specialization`. A temporary compiler wrapper applying only that flag then builds PyTorch3D against Torch 2.4.1 in 24 seconds; two imports and native CPU point/face and raster smokes pass.

## Required permanent fix

- Make uv's PyTorch3D extra build dependency match the runtime Torch.
- Gate `-Wno-invalid-specialization` narrowly to Apple Clang versions whose libc++ enforces the new annotation, unless upstream evidence identifies a smaller supported header-level remedy.
- Preserve a clean-build regression: exact runtime/build Torch match, arm64 artifact inspection, two-process import, point/face smoke, and raster smoke.
