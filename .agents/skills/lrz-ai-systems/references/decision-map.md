# LRZ AI Systems Decision Map

Start here, then read only the references needed for the current task.

## Always

- `lrz-original-sources.md` when a claim depends on current LRZ, Slurm, Pyxis,
  or EFM3D behavior.
- `cheatsheet.md` when the user needs a short operator command sequence.

## By Task

- SSH, project access, first login, or basic probe:
  `cheatsheet.md`, then `service-desk-templates.md` only if access is blocked.
- DSS layout, quota, datasets, caches, checkpoints, logs, containers, or temp
  files: `storage-dss.md`.
- Partition choice, GPU count, CPU jobs, `sinfo`, `squeue`, `sacct`, or job
  status: `slurm-partitions.md` and `slurm-job-patterns.md`.
- Interactive or batch containers: `containers-pyxis.md` and
  `slurm-job-patterns.md`.
- ARIA dataset/cache/training commands: `aria-workflows.md`.
- EFM3D, ASE, ATEK, EVL, or upstream EFM3D Slurm examples:
  `efm3d-aria-workloads.md`, then `storage-dss.md` and
  `slurm-job-patterns.md`.
- Failed jobs, pending reasons, missing logs, container launch failures, or
  suspicious remote output: `troubleshooting-slurm.md`, then hand off to
  the selected diagnostic capability if the failure is concrete and
  code/data-facing.
- Missing quota, project membership, MCML QOS, or DSS allocation:
  `service-desk-templates.md`, then hand off to `agents-db` only for durable
  blocked access or quota debt.

## Stop Conditions

- Do not submit jobs, change project storage, or send service-desk messages
  without explicit user authority.
- Do not continue reading references once the command shape, resource class,
  storage policy, and verification path are grounded.
