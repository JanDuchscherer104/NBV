# LRZ AI Systems Decision Map

Start here, then read only the references needed for the current task.

## Always

- Use `lrz-original-sources.md` when cluster behavior may have changed.
- Use the scripts directly for short operator command sequences.

## By Task

- SSH, project access, first login, or basic probe: `scripts/lrz-probe.sh` and
  the current LRZ access documentation.
- DSS layout, quota, datasets, caches, checkpoints, logs, containers, or temp
  files: `storage-dss.md`.
- Partition choice, GPU count, CPU jobs, or status: run
  `scripts/lrz-resources.sh`, then read `slurm-job-patterns.md`.
- Interactive or batch containers: `containers-pyxis.md` and
  `slurm-job-patterns.md`.
- Workload commands and scientific resource choices: hand off to the owning
  package or data skill; this skill supplies only the LRZ execution envelope.
- Failed jobs, pending reasons, missing logs, container launch failures, or
  suspicious remote output: `troubleshooting-slurm.md`, then hand off to
  the selected diagnostic capability if the failure is concrete and
  code/data-facing.
- Missing quota, project membership, QOS, or DSS allocation: capture the live
  error and hand durable blocked access or quota debt to `agents-db`.

## Stop Conditions

- Do not submit jobs, change project storage, or send service-desk messages
  without explicit user authority.
- Do not continue reading references once the command shape, resource class,
  storage policy, and verification path are grounded.
