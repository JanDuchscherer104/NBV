# Slurm Troubleshooting

Use this for concrete LRZ job failures, pending jobs, missing output, or
container launch issues.

## First Evidence

Capture exact job metadata once:

```bash
squeue -u "$USER" -o "%.18i %.20P %.30j %.8T %.10M %.6D %R"
sacct -j <JOB_ID> --format=JobID,JobName,Partition,State,Elapsed,AllocGRES,ExitCode
scontrol show job <JOB_ID>
```

Read the job's stdout/stderr under `$ARIA_DSS/logs/slurm/`. Do not run polling
loops around Slurm commands.

## Common Checks

- Pending with resource or policy reason: verify partition, QOS/account, time
  limit, memory, `--gres`, and MCML access.
- No GPU visible: verify `--gres=gpu:<N>`, partition, container CUDA stack, and
  `nvidia-smi` inside the allocation.
- Missing output file: check absolute `#SBATCH --output/--error` paths and that
  the log directory exists before submission.
- Container pull is slow: prefer a local `.sqsh` under `$ARIA_DSS/containers/`
  for repeated use.
- Python rebuilds or package downloads are slow: source `lrz-aria-env.sh` so uv,
  pip, torch, Hugging Face, W&B, and temp caches land on DSS.
- Multi-node Torchrun hangs: verify `MASTER_ADDR`, `MASTER_PORT`, node count,
  `SLURM_GPUS_ON_NODE`, and one launcher/container per node.

## Escalation

Hand off to the selected diagnostic capability when the failure includes ARIA code errors, data
contract errors, suspicious metrics, or reproducible logs beyond cluster setup.
Hand off to `agents-db` only for durable blocked access, quota, or project/QOS
debt.
