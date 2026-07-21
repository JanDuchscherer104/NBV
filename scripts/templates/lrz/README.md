# LRZ Slurm Templates

Most templates in this directory are dry-run contracts. The exception is
`rollout_generation.sbatch`, which is the real manifest-driven rollout array
launcher. It requires an explicit `sbatch --array=0-(NUM_SHARDS-1)` submission
and a project environment prepared before the array starts.

`qh_training_one_node.sbatch` is the real one-node Q_H training launcher. It
starts one Pyxis container task with `srun`, then lets one standalone TorchRun
launcher create one worker per allocated GPU through the checkout's prepared
`.venv` with `uv run --frozen --no-sync`. Set `ARIA_DSS`, `ARIA_REPO`, and
`QH_CONFIG`; optionally set `QH_RESUME` to an explicit full-state checkpoint.
The script rejects missing or mismatched GPU allocation, multi-node/per-GPU
task topology, missing frozen-environment preflights, and duplicate launcher
invocations before entering the container.

Before converting any template into a real job:

1. Inspect current ARIA console entry points from the LRZ checkout.
2. Replace placeholder commands such as `<ORACLE_GENERATION_ENTRYPOINT>`.
3. Confirm `ARIA_DSS`, quota, inode pressure, and the shard manifest.
4. Keep all large outputs, logs, caches, checkpoints, and containers under
   `$ARIA_DSS`.
5. Preserve the atomic-write and resume expectations documented in
   `.configs/lrz/README.md`.

## Template Variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `ARIA_DSS` | `/ABS/PATH/TO/ARIA_DSS` | DSS root for large ARIA artifacts. |
| `ARIA_REPO` | `$HOME/src/ARIA-NBV` | LRZ checkout path. |
| `LRZ_CONTAINER_IMAGE` | `nvcr.io#nvidia/pytorch:24.10-py3` | Enroot/Pyxis container image URI. |
| `RUN_ID` | workflow-specific dry-run ID | Run namespace for logs and staging. |
| `DATASET_VERSION` | placeholder | Dataset/cache/offline-store version. |
| `SHARD_MANIFEST` | workflow-specific path | Deterministic shard manifest. |

The `*_dry_run.sbatch` templates use Slurm comments and Pyxis options as
documentation and do not call `srun`. The real rollout template calls `srun`,
uses one manifest shard per array task, and never installs or synchronizes
dependencies inside array tasks.
