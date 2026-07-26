---
name: lrz-ai-systems
description: Operate ARIA-NBV jobs on LRZ.
metadata:
  mode: maintenance
  not_when:
    - "local-only work with no LRZ execution surface"
    - "scientific workload design or package semantics"
    - "credentialed or production action without user authority"
  handoff_to:
    - "dataset-cache-ops for dataset and cache contracts"
    - "nearest package owner for workload semantics"
    - "agents-db for durable access or quota blockers"
  evidence_required:
    - "live partition and DSS/container checks"
    - "dry-run, syntax check, or exact job-log excerpt"
  applies_to:
    - ".configs/lrz/**"
    - ".agents/skills/lrz-ai-systems/**"
  triggers:
    - "LRZ, Slurm, DSS, or Pyxis operation"
  must_read:
    - ".agents/skills/lrz-ai-systems/references/decision-map.md"
  canonical_sources:
    - ".agents/skills/lrz-ai-systems/references/decision-map.md"
    - ".agents/skills/lrz-ai-systems/references/lrz-original-sources.md"
    - ".agents/skills/lrz-ai-systems/references/storage-dss.md"
    - ".agents/skills/lrz-ai-systems/references/slurm-job-patterns.md"
    - ".agents/skills/lrz-ai-systems/references/containers-pyxis.md"
  verification:
    - "bash -n .agents/skills/lrz-ai-systems/scripts/*.sh"
    - "make check-agent-memory"
---

# LRZ AI Systems

Read `references/decision-map.md`, then only the reference selected there.
This skill owns environment and operator loops, not ARIA workload truth.

## Safety

- Use login nodes only for transfer, inspection, editing, and submission.
- Never run heavy work on login nodes or use `sudo`.
- Keep large artifacts and caches under `$ARIA_DSS`, not `$HOME`.
- Request GPUs explicitly with `--gres=gpu:<N>`.
- Query Slurm state once at runtime; never automate polling loops.
- Run containers through Pyxis inside Slurm allocations.
- Do not submit jobs or change remote storage without user authority.

## Operator Loop

1. Run `scripts/lrz-probe.sh`; initialize storage with `lrz-dss-init.sh`.
2. Inspect current resources with `scripts/lrz-resources.sh`.
3. Use `lrz-container-shell.sh` for an allocated interactive shell.
4. Use the retained parameterized sbatch scripts for CPU, GPU, or multi-GPU
   commands after checking current partition limits.
5. Verify allocation, GPU visibility, logs, and output before scaling.

Stop with the exact access, quota, allocation, or log evidence when the next
step needs credentials, remote authority, or workload-owner input.
