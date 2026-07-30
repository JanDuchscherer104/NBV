---
id: gotchas
updated: 2026-05-15
scope: repo
owner: jan
status: active
tags: [workflow, training, cache, frames]
---

# Gotchas

## Environment and Tooling
- Prefer `uv run --project aria_nbv pytest` or `aria_nbv/.venv/bin/python -m pytest`; the system interpreter may miss dependencies such as `power_spherical`.
- Assume the environment is working unless the user indicates otherwise, but verify the exact interpreter before concluding a dependency problem.
- `make context` refreshes the lightweight routing artifacts only; use targeted search on `source_index.md`, `literature_index.md`, and `data_contracts.md` instead of loading broad dumps.
- `make context-heavy` and the `context-uml`, `context-docstrings`, or `context-tree` targets are explicit fallback tools for architecture or refactor tasks.
- Local CUDA visibility does not imply PyTorch3D CUDA support. On 2026-05-13 the workstation saw an RTX 3080 Ti, but PyTorch3D rasterization and point-mesh distance raised `RuntimeError: Not compiled with GPU support`; on 2026-05-15 PyTorch3D CUDA rasterization was restored by rebuilding from the activated `aria-nbv` mamba toolchain. Keep the mamba toolchain env active, `CUDA_HOME=$CONDA_PREFIX`, `FORCE_CUDA=1`, and `TORCH_CUDA_ARCH_LIST=8.6` when reinstalling CUDA extensions.

## Training and Validation
- Validation is disabled by default unless `trainer_config.enable_validation=true`; otherwise Lightning forces `limit_val_batches=0` and `check_val_every_n_epoch=0`.
- Treat explicit user termination criteria as binding. If they imply stronger verification, expand the test plan rather than stopping at a smoke test.
- Prefer real-data or integration-style verification when feasible for package changes; do not rely only on mocks for end-to-end behavior claims.

## VIN Offline Stores and Splits
- The canonical offline training path is `VinOfflineDataset`, configured through `VinOfflineSourceConfig` with `kind = "offline"`.
- Offline store splits are file-backed NumPy arrays under `splits/`; rebuild stale stores with `VinOfflineWriter` rather than legacy cache-index repair helpers.
- `sample_index.jsonl` is the source of scene/snippet coverage and shard rows.
- `VinOracleBatch.collate` expects model-ready `VinSnippetView` instances rather than raw `EfmSnippetView` samples.

## Frames and Geometry
- Pose-frame consistency and CW90 corrections are easy to misuse across rendering and VIN inputs.
- Use `PoseTW` and `CameraTW` instead of raw matrices in normal package code.
- Document tensor shapes and coordinate frames when a contract is not obvious from the type alone.

## EVL / OBB
- EVL OBB outputs are not batch-collatable yet; entity-aware runs may need `batch_size=None` or OBB outputs disabled.
- Candidate validity heuristics and semidense visibility proxies are conservative; do not assume they are equivalent to training masks unless the training loop explicitly applies them.
- Full-scene RRI during target-rollout generation is much more expensive than target-cropped RRI. Keep scene RRI as an explicit audit option even when PyTorch3D CUDA is available; target RRI remains the thesis-core label.

## Config and Pydantic
- `Field(default=<callable>)` stores the callable itself; use `Field(default_factory=...)` for computed defaults.
- Prefer config-local `field_validator` and `model_validator` hooks for cross-field validation and coercion.
