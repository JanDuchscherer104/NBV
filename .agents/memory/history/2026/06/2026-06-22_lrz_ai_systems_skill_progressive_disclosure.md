---
id: 2026-06-22_lrz_ai_systems_skill_progressive_disclosure
date: 2026-06-22
title: "LRZ AI Systems Skill Progressive Disclosure"
status: done
topics: [lrz, slurm, efm3d, skills]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/lrz-ai-systems/SKILL.md
  - .agents/skills/lrz-ai-systems/references/decision-map.md
  - .agents/skills/lrz-ai-systems/references/lrz-original-sources.md
  - .agents/skills/lrz-ai-systems/references/slurm-job-patterns.md
  - .agents/skills/lrz-ai-systems/references/efm3d-aria-workloads.md
  - .agents/skills/lrz-ai-systems/references/troubleshooting-slurm.md
---

## Task

Patch the LRZ AI Systems skill after best-practice research so it has more
accurate nested context, better progressive disclosure, and less root-skill
clutter.

## Method

The root skill was reduced to activation, hard safety rules, a short workflow,
and verification. A new `decision-map.md` became the only required nested read.
LRZ, Slurm, Pyxis, and EFM3D source-sensitive facts were moved into focused
references, with EFM3D-specific LRZ translation kept separate from ARIA-NBV
entry-point guidance.

## Outputs

- Added source pointer, Slurm job pattern, EFM3D workload, and troubleshooting
  references.
- Moved fixed partition and EFM3D workload cautions out of the root skill.
- Kept credential/project/DSS examples as placeholders only.

## Verification

- `bash -n .agents/skills/lrz-ai-systems/scripts/*.sh`
- executable script listing with `find`
- skill validation with `quick_validate.py`
- secret/path placeholder scan
- ASCII scan over the skill and references
- `make check-agent-memory`

`shellcheck` was not installed in this environment, so shell linting was limited
to Bash syntax checks.

## Canonical State Impact

No canonical state update is needed. This is a workflow/guidance refactor within
the existing LRZ skill ownership surface.
