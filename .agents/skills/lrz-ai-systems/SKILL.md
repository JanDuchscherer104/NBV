---
name: lrz-ai-systems
description: Use for ARIA-NBV work on LRZ SSH, DSS, Slurm, Pyxis containers, remote data jobs, training, or job failures.
metadata:
  mode: maintenance
  not_when:
    - "local-only package, docs, or scaffold work with no LRZ execution surface"
    - "experiment design before a concrete remote resource or batch need exists"
    - "credential, quota, or production action that lacks user authority"
  handoff_to:
    - "dataset-cache-ops for ASE shards, offline stores, and data smoke contracts"
    - "nearest rollout package owner for rollout or Q_H workload semantics"
    - "specialized diagnostic capability for failed jobs or suspicious output"
    - "agents-db for durable blocked access, quota, or remote-run debt"
  evidence_required:
    - "target LRZ partition, DSS/container path policy, and intended workload class"
    - "dry-run, syntax check, or exact Slurm/job log excerpt"
    - "explicit credential/access blocker when remote verification cannot run"
  applies_to:
    - ".configs/lrz/**"
    - "scripts/templates/**"
    - ".agents/skills/lrz-ai-systems/**"
    - "docs/contents/setup.qmd"
  triggers:
    - "LRZ"
    - "Slurm"
    - "DSS"
    - "Pyxis"
    - "EFM3D on LRZ"
  must_read:
    - ".agents/skills/lrz-ai-systems/references/decision-map.md"
  canonical_sources:
    - ".agents/skills/lrz-ai-systems/references/decision-map.md"
    - ".agents/skills/lrz-ai-systems/references/lrz-original-sources.md"
    - ".agents/skills/lrz-ai-systems/references/storage-dss.md"
    - ".agents/skills/lrz-ai-systems/references/slurm-partitions.md"
    - ".agents/skills/lrz-ai-systems/references/slurm-job-patterns.md"
    - ".agents/skills/lrz-ai-systems/references/containers-pyxis.md"
    - ".agents/skills/lrz-ai-systems/references/efm3d-aria-workloads.md"
    - ".agents/skills/lrz-ai-systems/templates/sbatch_single_gpu_aria.sh"
  literature_refs:
    - "docs/contents/thesis/roadmap.qmd"
  verification:
    - "shellcheck or dry-run checks for changed scripts where available"
    - "make check-agent-memory for LRZ guidance changes"
---

# LRZ AI Systems

## OMX Integration

OMX may plan or supervise remote work, but this skill only provides ARIA/LRZ
environment knowledge and evidence loops. It should return concrete command
shapes, resource constraints, and blockers without assuming credentials,
submitting jobs, or owning workflow state.

## Read First

- `references/decision-map.md` first. It routes to the smallest nested
  reference set for the current LRZ task.
- `references/lrz-original-sources.md` when LRZ, Slurm, Pyxis, or EFM3D facts
  could be stale or source-sensitive.

## Rules

- Use `login.ai.lrz.de` login nodes only for editing, transfer, inspection, and Slurm submission.
- Never run heavy computation on login nodes.
- Never use `sudo`.
- Keep code, small config, SSH/git config, and non-committed NGC credentials in `$HOME`.
- Keep large datasets, generated caches, checkpoints, Slurm/W&B logs,
  containers, temp files, and package/model caches under `$ARIA_DSS`.
- Never submit GPU work without `--gres=gpu:<N>`.
- Do not automate `sinfo`, `squeue`, `sacct`, or similar Slurm polling loops.
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
7. Read `references/aria-workflows.md` or `references/efm3d-aria-workloads.md`
   before filling dataset, cache, or training commands.

## Verification

- `bash -n .agents/skills/lrz-ai-systems/scripts/*.sh`
- `find .agents/skills/lrz-ai-systems/scripts -maxdepth 1 -type f -perm -111`
- Run a secret/path scan for credential terms, personal LRZ usernames, fixed DSS paths, and host-local absolute paths.
- `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/lrz-ai-systems`
- `make check-agent-memory`
- `make agents-db AGENTS_ARGS='validate'` only when agents DB files changed.
