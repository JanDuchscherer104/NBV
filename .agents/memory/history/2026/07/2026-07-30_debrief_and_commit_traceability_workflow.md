---
id: 2026-07-30_debrief_and_commit_traceability_workflow
date: 2026-07-30
title: "debrief and commit traceability workflow"
status: done
topics: [scaffold, debriefs, commits, agents-db]
confidence: high
canonical_updates_needed: []
---

## Task
Separate temporary cross-session handoffs from durable ARIA-NBV execution
debriefs, and make meaningful commits traceable to their existing records.

## Method
Compared the current upstream `mattpocock/skills` `ask-matt` and `handoff`
contracts with the repository memory and Agents DB owners; then added the
smallest repo-local closeout skill and routing pointers.

## Findings
- Installed the current upstream user-level `ask-matt` router under
  `~/.codex/skills/ask-matt`; it is available on the next Codex turn.
- Added `.agents/skills/debriefs/SKILL.md`. It makes `$handoff` a temporary,
  untracked context bridge, while native debriefs remain concise durable
  execution evidence.
- Updated `AGENTS.md`, `agent-behavior`, and `.agents/memory/README.md` so
  coherent verified slices are committed promptly and meaningful commits point
  to their debrief and relevant Agents DB records using footer references.

## Verification
- `python3 /home/jd/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/debriefs` passed.
- `make check-agent-memory` passed.
- `make agents-db AGENTS_ARGS='validate'` passed.
- `make agents-db` completed; no DB record changed because this work created no
  active maintenance debt.

## Canonical State Impact
No `.agents/memory/state/` update is needed. Durable workflow behavior lives in
the new `debriefs` skill and the root/agent-behavior routing guidance.
