---
id: 2026-05-06_agents_scaffold_proposal_requirements_alignment
date: 2026-05-06
title: "Agents Scaffold Proposal Requirements Alignment"
status: done
topics: [agents-db, scaffold, memory, proposal]
confidence: high
canonical_updates_needed:
  - .agents/AGENTS_INTERNAL_DB.md
  - .agents/skills/agents-db/SKILL.md
  - .agents/memory/README.md
  - .agents/issues.toml
  - .agents/todos.toml
  - .agents/resolved.toml
  - aria_nbv/aria_nbv/rollouts/AGENTS.md
  - docs/contents/thesis/questions.qmd
files_touched:
  - .agents/AGENTS_INTERNAL_DB.md
  - .agents/skills/agents-db/SKILL.md
  - .agents/memory/README.md
  - .agents/issues.toml
  - .agents/todos.toml
  - .agents/resolved.toml
  - .agents/skills/counterfactual-rollout-planner/SKILL.md
  - .agents/memory/history/2026/05/2026-05-06_agents_scaffold_proposal_requirements_alignment.md
---

## Task

Consolidate extracted proposal requirements into the agents scaffold without
creating duplicate backlog records or a standalone proposal-requirements memory
file.

## Outputs

- Updated the agents DB interface text so extracted proposal, transcript, and
  review requirements route to active `.agents/*.toml` records, canonical state,
  or dated debriefs according to ownership.
- Amended existing proposal, bibliography, Q_H, and doc-polish records instead
  of adding new records.
- Replaced stale legacy research-question anchors in active and resolved agent
  records with current five-RQ anchors.
- Aligned the rollout-planner skill link with the current RQ4 planning anchor.

## Verification

- `make agents-db AGENTS_ARGS='validate'`
- `make agents-db`
- `python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-creator/scripts/quick_validate.py" .agents/skills/agents-db`
- `make check-agent-memory`
- Stale Q_H wording and legacy research-question anchor scan over `.agents`.

## Canonical State Impact

No `.agents/memory/state/` file was changed. The scaffold and active backlog now
point at the existing current thesis truth rather than restating it in a new
memory surface.
