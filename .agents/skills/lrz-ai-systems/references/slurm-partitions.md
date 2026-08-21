# Slurm Partitions

Use `sinfo` at runtime for current partitions, states, and time limits. Documentation and local notes can become stale.

## One-Shot Queries

```bash
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh summary
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh gpu
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh cpu
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh partition lrz-v100x2
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh nodes lrz-v100x2
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh mine
```

Do not run Slurm status commands in tight loops.

## Defaults

- GPU smoke test: `lrz-v100x2`, 1 GPU, 10 minutes.
- CPU preprocessing: `lrz-cpu`, often with `--qos=cpu`.
- Small cache test: `lrz-v100x2` or an A100 80GB partition.
- Serious cache/training: H100 or A100 80GB partitions.
- Multi-GPU: only after the single-GPU path works.
- MIG: small experiments only, not large rendering/cache jobs.
- MCML partitions: use only after access/QOS is confirmed by project membership or a short successful test allocation.

## Common Partition Patterns

```text
lrz-v100x2                 smoke/debug
lrz-hpe-p100x4             legacy/debug
lrz-dgx-1-p100x8           legacy
lrz-dgx-1-v100x8           V100 jobs
lrz-dgx-a100-80x8          A100 80GB jobs
lrz-hgx-a100-80x4          A100 80GB jobs
lrz-dgx-a100-40x8-mig      MIG slices
lrz-hgx-h100-94x4          H100 jobs
lrz-cpu                    CPU-only
mcml-*                     require confirmed MCML access/QOS
```

## GPU Requirement

Always include `--gres=gpu:<N>` for GPU allocations and batch jobs. Missing GRES can leave jobs pending with policy errors or allocate no GPU.

Allocation, batch-script, and troubleshooting routes are selected directly by
the decision map.
