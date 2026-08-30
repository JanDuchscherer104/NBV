# ARIA-NBV Setup

This guide is the portable setup path for the local research environment. Keep
machine-specific mounts, cluster paths, and private notes out of this file; put
them in local shell config or internal operator references instead.

## 1. Clone and submodules

```sh
git clone https://github.com/JanDuchscherer104/ARIA-NBV.git
cd ARIA-NBV
git submodule update --init --recursive
```

The Python package is under `aria_nbv/`. EFM3D and OpenPoints are installed from
the repo-local sources under `external/`, so those submodules must exist before
`uv sync`.

If `external/efm3d` does not point at the ARIA-NBV fork, add it as an additional
remote and pull the expected branch:

```sh
cd external/efm3d
git remote -v
git remote add fork https://github.com/JanDuchscherer104/efm3d.git
git fetch fork
git checkout main
git pull fork main
cd ../..
```

## 2. Python and CUDA environment

Use Python 3.11. On Linux GPU machines, create the toolchain environment first
so CUDA 12.1, cuDNN, GCC, Ninja, and `uv` are available for PyTorch3D and
OpenPoints builds:

```sh
cd aria_nbv
mamba env create -f environment.yml
mamba activate aria-nbv
uv sync --all-extras
```

If `uv` cannot find Python 3.11 automatically, provide a local interpreter:

```sh
cd aria_nbv
UV_PYTHON=/path/to/python3.11 uv sync --all-extras
```

Check that commands use the repo venv before diagnosing dependency problems:

```sh
cd aria_nbv
.venv/bin/python --version
uv run python --version
uv run python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("cuda_version", torch.version.cuda)
PY
```

Torch CUDA availability is not sufficient for the rollout/oracle renderer.
PyTorch3D is compiled locally and must pass its own CUDA rasterization smoke.
The project backend preflight runs that smoke and records the result:

```sh
cd aria_nbv
PYTORCH3D_BACKEND=cuda uv run nbv-pytorch3d-backend
```

### CPU and GPU expectations

CPU-only machines are suitable for docs work, config validation, lightweight
tests, immutable-store reads, and the synthetic rollout trace smoke command.
They are not the expected path for full ASE oracle generation, EVL backbone
materialization, PyTorch3D depth rendering, or VIN training.

Linux GPU machines are the expected path for the thesis data loop. The package
pins PyTorch CUDA 12.1 wheels on Linux, and `environment.yml` provides a CUDA
12.1 toolchain for extension builds. Several configs use `device = "auto"` and
will fall back to CPU when CUDA is unavailable, but a CPU fallback is a
debugging convenience, not a performance target.

Use the `aria-nbv` mamba environment as the CUDA build-toolchain context and
the repo `.venv` as the `uv` runtime. Run the admission helper after `uv sync`;
it derives the exact Git source from `uv.lock`, rebuilds only PyTorch3D when
needed, and proves a real CUDA rasterization before succeeding:

```sh
mamba activate aria-nbv
cd aria_nbv
uv sync --locked --extra dev
cd ..
python3 scripts/setup_pytorch3d_cuda.py --cuda-home "$CONDA_PREFIX"
```

Run the helper again after any later `uv sync` that replaces PyTorch3D. It
leaves all locked transitive dependencies untouched.

### Optional xFormers

EFM3D attention utilities can use xFormers on Linux:

```sh
cd aria_nbv
uv sync --extra xformers
```

### Optional OpenPoints build toggles

OpenPoints is built through `external/openpoints_shim` during `uv sync`.
PointNet2 batch and Chamfer ops are the default useful path.

```sh
git submodule update --init --recursive external/PointNeXt external/openpoints_shim
cd aria_nbv
uv sync --all-extras

OPENPOINTS_BUILD_POINTOPS=1 uv sync --all-extras
OPENPOINTS_BUILD_SUBSAMPLING=1 uv sync --all-extras
OPENPOINTS_BUILD_CHAMFER_DIST=0 uv sync --all-extras
OPENPOINTS_BUILD_EMD=1 uv sync --all-extras
```

If extension builds cannot find `nvcc`, set `CUDA_HOME` or
`OPENPOINTS_TORCH_CUDA_ARCH_LIST` for the local machine.

### Apple Silicon geometry lane

Linux remains the default production lane and resolves PyTorch3D from the
pinned upstream CUDA-capable provider. On Darwin arm64, the package resolves
PyTorch3D from the pinned Mojo-enabled fork:

```sh
cd aria_nbv
uv sync --locked --extra dev
PYTORCH3D_BACKEND=mojo uv run nbv-pytorch3d-backend
```

`PYTORCH3D_BACKEND=auto` prefers CUDA when available, otherwise the
Mojo-enabled provider on Apple Silicon, otherwise CPU. Forced `cuda` and
`mojo` modes fail early when the requested provider cannot run; they do not
silently fall back. The `nbv-pytorch3d-backend` command prints the resolved
backend, Torch version, PyTorch3D source URL/SHA, platform, device, and
provider counters as JSON for experiment artifacts.

This Mac lane is intended for smaller deterministic agentic experiments and
overnight research loops. Full-scale CUDA generation, training, and OpenPoints
extension workloads remain Linux/Ubuntu responsibilities.

On macOS, Python ignores `.pth` files carrying the filesystem `hidden` flag.
If a console entry point cannot import `aria_nbv` although `uv run python` can,
repair the local environment metadata and resync it:

```sh
chflags -R nohidden .venv
uv sync --locked --extra dev
```

After pulling the `real-data-smoke` family, validate the complete public
geometry path and create one disposable immutable VIN store:

```sh
cd aria_nbv
PYTORCH3D_BACKEND=mojo uv run pytest -q \
  tests/integration/test_oracle_rri_labeler_real_data.py::test_oracle_rri_labeler_runs_real_data
PYTORCH3D_BACKEND=mojo uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_macos_smoke.toml --dry-run
PYTORCH3D_BACKEND=mojo uv run nbv-build-offline \
  --config-path ../.configs/build_vin_offline_macos_smoke.toml
```

## 3. Dataset and cache layout

ARIA-NBV expects paths to be rooted at the repository by default:

| Path | Purpose |
| --- | --- |
| `.data/aria_download_urls/` | Project Aria download URL JSON files. |
| `.data/ase_efm/<scene_id>/shards-*.tar` | ATEK EFM WebDataset shards used by the package. |
| `.data/ase_meshes/scene_ply_<scene_id>.ply` | ASE ground-truth meshes. |
| `.data/ase_meshes_processed/` | Generated cropped or simplified mesh artifacts. |
| `.data/offline_cache/vin_offline/` | Default immutable VIN offline store. |
| `.data/offline_cache/vin_offline_rerun_smoke_v7/` | One-sample sidecar store used by Rerun smoke docs. |
| `.logs/ckpts/` | External model checkpoints such as EVL, DINOv2, and PointNeXt. |
| `.logs/checkpoints/` | Lightning checkpoints produced by training. |
| `.artifacts/rerun/` | Saved Rerun `.rrd` recordings. |
| `.artifacts/rollouts/` | Synthetic or generated rollout trace artifacts. |

Relative immutable-store names such as `vin_offline` resolve under
`PathConfig().offline_cache_dir`, whose default is `.data/offline_cache`.
Use copied local TOML configs with absolute paths when a machine needs a
different data mount.

To exchange allowlisted ignored artifacts with `ssh ubuntu
~/repos/ARIA-NBV`, use the guarded helper (dry-run by default):

```sh
python3 scripts/sync_ubuntu_artifacts.py graphify-cache pull
python3 scripts/sync_ubuntu_artifacts.py graphify-cache pull --apply
python3 scripts/sync_ubuntu_artifacts.py real-data-smoke pull --apply
python3 scripts/sync_ubuntu_artifacts.py research-snapshot pull --apply
```

Only the content-addressed Graphify semantic cache supports pull and push, and
both directions are union-only. The real-data family pulls three immutable
scene-81283 files used by the Mac integration suite. Research material is
pulled into `.agents/work/remote/ubuntu/<remote-commit>/`; it never overwrites
local `.agents/work`, `.omx`, literature owners, or generated Graphify state.
Generated `graphify-input` and `graphify-out` remain revision-local; only their
content-addressed semantic cache crosses hosts. Code, skills, durable agent
memory, reviewed plans/specs, and tracked literature move through Git and PRs.
Virtual environments, `.env`, OMX runtime state, Codex databases, credentials,
and the dirty Ubuntu checkout are never mirrored. No family uses deletion or
in-place mutation.

## 4. ASE access and model weights

Request ASE access through the Project Aria dataset page, then place the
download manifests here:

```text
.data/aria_download_urls/ase_mesh_download_urls.json
.data/aria_download_urls/AriaSyntheticEnvironment_ATEK_download_urls.json
```

List available GT-mesh scenes:

```sh
cd aria_nbv
uv run nbv-downloader -m list -c efm -n 10
```

Download a small local subset before building caches:

```sh
cd aria_nbv
uv run nbv-downloader -m download -c efm --ns 1 --max-shards 1
```

Download external checkpoints into `.logs/ckpts/`:

```text
.logs/ckpts/model_lite.pth
.logs/ckpts/dinov2_vitb14_reg4_pretrain.pth
.logs/ckpts/s3dis-train-pointnext-s-ngpus1-seed1742-20220525-162639-Gz4ViiL95b6KP9MMH2ytG3_ckpt_best.pth
```

The default VIN config resolves Lightning checkpoints from `.logs/checkpoints/`.
For example, `.configs/offline_only.toml` references
`epoch=20-step=1869-train-loss=6.2684.ckpt`.

## 5. Offline store and VIN diagnostics

Validate the default VIN offline store before training from it:

```sh
cd aria_nbv
uv run nbv-summary --config-path offline_only.toml
```

The summary command forces `run_mode = "summarize_vin"`, disables W&B, uses one
batch, and reads the configured offline store. The current default
`.configs/offline_only.toml` points at `vin_offline`. Treat a manifest with
`"interrupted": true` as a diagnostic store rather than a full training store.

Build the current full-store config only after the one-scene path is healthy:

```sh
cd aria_nbv
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_81286.toml --dry-run
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_81286.toml
```

## 6. One-scene smoke path

Use the sidecar smoke config first. It writes exactly one sample to
`.data/offline_cache/vin_offline_rerun_smoke_v7/` and is safe to overwrite.

```sh
cd aria_nbv
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_rerun_smoke_v7.toml --dry-run
uv run nbv-build-offline --config-path ../.configs/build_vin_offline_rerun_smoke_v7.toml
```

Save a Rerun recording from that one sample:

```sh
cd aria_nbv
uv run nbv-rerun-inspect --config-path ../.configs/rerun_offline_smoke_v7.toml --split val --index 0 --save ../.artifacts/rerun/offline_smoke_v7.rrd
```

Open the saved recording in the native viewer when available:

```sh
cd aria_nbv
uv run nbv-rerun-inspect --config-path ../.configs/rerun_offline_smoke_v7.toml --split val --index 0 --view
```

The Rerun inspector is diagnostic-only. Its point and mesh downsampling are
display-only and must not be treated as label, ranking, or training changes.

## 7. Training and app entry points

```sh
cd aria_nbv

# Streamlit diagnostics app
uv run nbv-st

# VIN one-batch diagnostic summary
uv run nbv-summary --config-path offline_only.toml

# VIN training from the immutable offline store
uv run nbv-train --config-path offline_only.toml

# Fit and save the ordinal binner
uv run nbv-fit-binner --config-path offline_only.toml

# Dump resolved config
uv run nbv-cli --run-mode dump-config --config-path offline_only.toml
```

Use the Streamlit VIN diagnostics page to inspect offline-store coverage,
tensor shapes, candidate/RRI alignment, and model debug outputs before trusting
new training runs.

## 8. Docs sanity commands

Run these after setup-doc or smoke-doc edits:

```sh
make qmd-frontmatter-check
cd docs
quarto render contents/setup.qmd
quarto render contents/impl/one_scene_smoke.qmd
quarto render contents/impl/rerun_offline_inspector.qmd
quarto check
```

For a full docs build, use:

```sh
cd docs
quarto render .
```
