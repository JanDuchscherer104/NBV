---
name: lrz-ai-systems
description: "Use when working with LRZ AI Systems remote compute for ARIA-NBV: SSH/login.ai.lrz.de, DSS storage, Slurm GPU/CPU allocations, Enroot/Pyxis containers, dataset/cache/training batch jobs, or debugging remote job failures."
---

# LRZ AI Systems

## OMX Integration

OMX may plan or supervise remote work, but this skill only provides ARIA/LRZ
environment knowledge and evidence loops. It should return concrete command
shapes, resource constraints, and blockers without assuming credentials,
submitting jobs, or owning workflow state.

## Read First

- [`references/decision-map.md`](references/decision-map.md) first. It routes
  to the smallest nested
  reference set for the current LRZ task.
- Read [`references/lrz-original-sources.md`](references/lrz-original-sources.md)
  when LRZ, Slurm, Pyxis, or EFM3D facts could be stale or source-sensitive.
- For a failed job or container start, read
  [`references/troubleshooting-slurm.md`](references/troubleshooting-slurm.md)
  after the decision map, capture one metadata snapshot plus stdout/stderr, and
  hand off concrete ARIA or data failures.
- For current external dependency API or version uncertainty, route through
  [`aria-nbv-context`](../aria-nbv-context/SKILL.md) and its
  [`Context7 registry`](../aria-nbv-context/references/context7_library_ids.md);
  keep library IDs and plugin calls in that owner.

## Rules

- Use `login.ai.lrz.de` login nodes only for editing, transfer, inspection, and Slurm submission.
- Never run heavy computation on login nodes.
- Never use `sudo`.
- Keep code, small config, SSH/git config, and non-committed NGC credentials in `$HOME`.
- Keep large datasets, generated caches, checkpoints, Slurm/W&B logs,
  containers, temp files, and package/model caches under `$ARIA_DSS`.
- Never submit GPU work without `--gres=gpu:<N>`.
- Do not automate `sinfo`, `squeue`, `sacct`, or similar Slurm polling loops.
- Do not silently poll or submit jobs, or guess partition, container, or
  resource settings; require explicit authority for submission and report
  missing evidence as a blocker.
- Use current `sinfo` output at runtime; partition names and limits can change.
- Avoid MCML partitions unless access/QOS is confirmed by project membership or a short successful test allocation.
- Use Pyxis Slurm options (`--container-image`, `--container-mounts`) for containers on compute nodes.
- For LRZ jobs, prefer containerized workloads. Inside the container, use the
  project environment manager with caches on DSS.

## Standard Workflow

1. Inspect access and storage with `scripts/lrz-probe.sh` and `dssusrinfo all`.
2. Choose or request an AI Systems DSS container, then run `scripts/lrz-dss-init.sh "$ARIA_DSS"`.
3. Inspect partitions once with `scripts/lrz-resources.sh summary` or `scripts/lrz-resources.sh gpu`.
4. Smoke test GPU access with `salloc -p lrz-v100x2 --gres=gpu:1 --time=00:10:00` and `srun --pty bash`.
5. Use `scripts/lrz-container-shell.sh` inside an allocation for interactive container debugging.
6. Use `scripts/lrz-sbatch-cpu.sh`, `scripts/lrz-sbatch-single-gpu.sh`, or `scripts/lrz-sbatch-multigpu.sh` for batch work.
7. Read [`references/aria-workflows.md`](references/aria-workflows.md) or
   [`references/efm3d-aria-workloads.md`](references/efm3d-aria-workloads.md)
   before filling dataset, cache, or training commands.

## Verification

- `bash -n .agents/skills/lrz-ai-systems/scripts/*.sh`
- `find .agents/skills/lrz-ai-systems/scripts -maxdepth 1 -type f -perm -111`
- Run a secret/path scan for credential terms, personal LRZ usernames, fixed DSS paths, and host-local absolute paths.
- `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/lrz-ai-systems`
- `make check-agent-memory`
- `make agents-db AGENTS_ARGS='validate'` only when agents DB files changed.
