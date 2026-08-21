# Slurm Job Patterns

Use this when shaping allocations or batch scripts after the decision map has
selected the relevant resource path.
Run live one-shot checks before choosing final resources.

## Interactive Smoke

Use interactive allocations for short setup, debugging, GPU visibility, and
container smoke tests.

```bash
salloc -p lrz-v100x2 --gres=gpu:1 --time=00:10:00
srun --pty bash
nvidia-smi
```

Keep requests small and short unless the user has explicitly asked for a larger
debug allocation.

## Batch Jobs

- Prefer `sbatch` for long-running workloads.
- Put absolute paths in `#SBATCH --output` and `#SBATCH --error`; shell
  variables are not expanded in `#SBATCH` directives at submission time.
- Use `srun` for the managed compute step inside the batch allocation.
- Put Slurm logs under `$ARIA_DSS/logs/slurm/`.

## GPU Requests

- Always request GPUs with `--gres=gpu:<N>` on GPU partitions.
- On multi-node jobs, `--gres=gpu:<N>` is GPUs per node, not total GPUs.
- Match `--ntasks-per-node` to the launcher. Torchrun commonly uses one
  container/process launcher per node and `--nproc_per_node=$SLURM_GPUS_ON_NODE`.
- Do not assume `--gres=gpu:8` works on every serious partition. Current LRZ H100
  and HGX A100 nodes expose 4 GPUs per node; DGX A100 and DGX-1 nodes expose 8.

## Containerized Steps

Use Pyxis options on the `srun` step unless an LRZ example explicitly puts the
container options in the batch preamble.

```bash
srun --ntasks=1 \
  --container-image="$LRZ_CONTAINER_IMAGE" \
  --container-mounts="$HOME:$HOME,$ARIA_DSS:$ARIA_DSS,$ARIA_REPO:$ARIA_REPO" \
  bash -lc 'cd "$ARIA_REPO" && source .agents/skills/lrz-ai-systems/scripts/lrz-aria-env.sh "$ARIA_DSS" && exec bash'
```

## Templates

- CPU preprocessing: `templates/sbatch_cpu_dataset_prep.sh`
- Single-GPU smoke/cache job: `templates/sbatch_single_gpu_aria.sh`
- Multi-GPU Torchrun job: `templates/sbatch_multigpu_torchrun_aria.sh`

Use the wrapper scripts for ordinary ARIA runs:

- `../scripts/lrz-sbatch-cpu.sh`
- `../scripts/lrz-sbatch-single-gpu.sh`
- `../scripts/lrz-sbatch-multigpu.sh`
