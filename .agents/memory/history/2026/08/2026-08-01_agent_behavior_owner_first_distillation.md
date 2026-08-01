---
id: 2026-08-01_agent_behavior_owner_first_distillation
date: 2026-08-01
title: "Agent Behavior Owner-First Distillation"
status: done
topics: [scaffold, agent-behavior, progressive-disclosure]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/agents/openai.yaml
  - .agents/skills/agent-behavior/references/durable-capture.md
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/references/human_owner_intent.md
---

## Task

Distill `agent-behavior` into the accepted compact operational kernel while
preserving durable-capture and external-action safeguards through progressive
disclosure.

## Method And Findings

Collapsed repeated principles, lane rules, workflow, and completion prose into
one checkable owner-first loop. Moved rare durable-capture and Git/external-action
branches into precise skill-local references. Removed the duplicate capture
destination table from human intent; `.agents/references/source_order.md` remains
its sole owner.

A follow-up review against the accepted governing principles and the external
Karpathy guidelines restored their universal behavioral core directly in the
loop: bounded retrieval, explicit ambiguity and tradeoffs, simplest/native-first
selection, surgical changes, goal-driven verification, single ownership, and
capability-preserving cleanup. External wording remains evidence rather than a
second ARIA authority.

Root guidance and shared Graphify, MemPalace, domain-skill, and scaffold-audit
surfaces were left untouched because other active tasks own those changes.

## Verification

- Focused capture-and-routing governance test passed.
- Skill `quick_validate.py` passed.
- `make scaffold-audit` passed with 21 unrelated/pre-existing warnings, one
  fewer than the baseline because the skill no longer trips semantic-drift lint.
- Path-scoped `git diff --check` passed.
- `make check-agent-memory` remained blocked by concurrent tracked
  `.codex/skills/graphify/**` changes; the same unrelated blocker existed before
  this edit.

## Canonical-State Impact

No project scientific or implementation state changed. The accepted scaffold
specification, source-order capture map, and human preferences remain the durable
owners for their respective meanings.
