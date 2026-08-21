# ARIA Workflows On LRZ

Use this for ARIA-NBV commands. The decision map selects the dedicated EFM3D
workload route when a command comes from facebookresearch/efm3d, ASE, ATEK, or
EVL rather than an ARIA-NBV entry point.

## Before Filling Commands

Inspect current ARIA console scripts before writing cache or training commands:

```bash
cd aria_nbv
uv run python - <<'PY'
import importlib.metadata as m
for ep in m.entry_points().select(group="console_scripts"):
    if "nbv" in ep.name or "aria" in ep.name:
        print(ep.name, "->", ep.value)
PY
```

Do not invent permanent CLI names. Use placeholders in templates when the current command is unknown.

## Smoke Commands

```bash
cd aria_nbv
uv run pytest tests/test_panels_dispatcher.py -q
uv run python -c 'import torch; print(torch.cuda.is_available())'
```

## Batch Wrappers

CPU preprocessing:

```bash
ARIA_DSS=/dss/.../aria-nbv \
  .agents/skills/lrz-ai-systems/scripts/lrz-sbatch-cpu.sh \
  'uv run pytest tests/test_panels_dispatcher.py -q'
```

Single-GPU smoke:

```bash
ARIA_DSS=/dss/.../aria-nbv \
LRZ_PARTITION=lrz-v100x2 \
LRZ_TIME=00:30:00 \
  .agents/skills/lrz-ai-systems/scripts/lrz-sbatch-single-gpu.sh \
  'uv run python -c "import torch; print(torch.cuda.is_available())"'
```

Multi-GPU training placeholder:

```bash
ARIA_DSS=/dss/.../aria-nbv \
LRZ_PARTITION=lrz-hgx-h100-94x4 \
LRZ_GPUS=2 \
  .agents/skills/lrz-ai-systems/scripts/lrz-sbatch-multigpu.sh \
  '<TRAIN_MODULE_OR_SCRIPT> <ARGS>'
```

## Data Placement

Keep all generated datasets, oracle caches, VIN stores, checkpoints, logs, W&B runs, temp files, and package/model caches under `$ARIA_DSS`.

Large EFM3D/ASE downloads should follow the decision map's dedicated workload
route before being mixed into ARIA cache or training jobs.
