# DSS Storage

LRZ AI Systems DSS is the default home for high-intensity AI I/O. Home
directories are for code and small configuration only.

## Placement Rules

- Store code, small configs, SSH config, git config, and non-committed NGC credentials in `$HOME`.
- Store large workload artifacts under `$ARIA_DSS`, never under `$HOME`.
- Put input data in `$ARIA_DSS/data/raw/`.
- Put processed data in `$ARIA_DSS/data/processed/`.
- Put generated caches in `$ARIA_DSS/caches/`.
- Put checkpoints in `$ARIA_DSS/checkpoints/`.
- Put Slurm logs in `$ARIA_DSS/logs/slurm/`.
- Put W&B logs in `$ARIA_DSS/logs/wandb/`.
- Put local `.sqsh` images in `$ARIA_DSS/containers/`.
- Put temporary files and package/model caches in `$ARIA_DSS/tmp/` and `$ARIA_DSS/.cache/`.

## Recommended Layout

```text
$ARIA_DSS/
  repo/
  data/raw/
  data/processed/
  caches/
  checkpoints/
  logs/slurm/
  logs/wandb/
  containers/
  tmp/
  .cache/uv/
  .cache/pip/
  .cache/huggingface/
  .cache/torch/
```

## Operator Notes

- Use `dssusrinfo all` to inspect accessible DSS containers and quota.
- Use `scripts/lrz-dss-init.sh "$ARIA_DSS"` to create the layout.
- Prefer tar shards, archives, HDF5, TFRecord, WebDataset-style shards, Zarr, or immutable chunked stores.
- Avoid millions of loose files and repeated directory scans on GPFS/DSS.
- Request more DSS quota before filling transitional or small per-user allocations.
