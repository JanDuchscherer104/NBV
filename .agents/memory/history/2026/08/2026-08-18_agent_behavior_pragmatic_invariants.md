---
id: 2026-08-18_agent_behavior_pragmatic_invariants
date: 2026-08-18
title: "Agent Behavior Pragmatic Invariants"
status: done
topics: [agent-scaffold, agent-behavior, pragmatic-programmer, guidance]
confidence: high
canonical_updates_needed: []
files_touched:
  - AGENTS.md
  - .agents/skills/agent-behavior/SKILL.md
  - scripts/tests/test_agent_governance_g002.py
---

## Task

Rebase the Matt-guidance pull-request branch onto current `origin/main` and
promote the remaining execution invariants from the reviewed scaffold sources
into their procedural owner without expanding the skill into a handbook.

## Method

Compared the rebased skill with the accepted scaffold target state, the trusted
external-practice report, the prior Pragmatic Programmer crosswalk,
`writing-for-agents`, and `codebase-design`. Kept requirements and general human
preferences in their existing owners and changed only the universal execution
procedure plus its root pointer.

## Findings

- Root guidance named failure-first diagnosis as an `agent-behavior` procedure
  while also carrying part of the procedure itself; the skill had no matching
  branch.
- Result contracts needed an explicit fail-fast bound, and literal verification
  needed to distinguish setup, health, freshness, and success states.
- Changeability is operationalized by a small owner interface, interface-level
  proof, and evidence before adding seams, adapters, or abstractions.
- Uncertain work needs an explicit retained tracer-slice versus disposable
  prototype choice and an artifact disposition.

## Verification

The focused scaffold, memory, Graphify, and governance checks were run on the
rebased branch before publication.

## Canonical-State Impact

`agent-behavior` now owns the repeatable failure-first, fail-fast,
change-locality, literal-status, and reversible-learning procedures. Root
`AGENTS.md` remains the compact activation pointer; the accepted specification,
human-owner intent, code, tests, and configuration retain their existing scope.
