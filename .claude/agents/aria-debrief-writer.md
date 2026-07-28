---
name: aria-debrief-writer
description: Use to write a compact debrief under .agents/memory/history/YYYY/MM/ for a non-trivial ARIA-NBV task. Follows agent_memory_templates.md and runs make check-agent-memory.
tools: Read, Bash, Edit, Write
model: inherit
---

Read `.agents/references/agent_memory_templates.md` first. Then:

1. Run `make new-debrief TITLE="<short title>"` to scaffold today's file under
   `.agents/memory/history/YYYY/MM/`.
2. Fill the body concisely:
   - task (one sentence: the goal)
   - method or commands (what was actually run)
   - findings or outputs (what changed; cite file paths)
   - verification (commands; pass/fail; blockers)
   - current-owner impact
3. Set `canonical_updates_needed`:
   - empty list if the task did not change current truth (say so explicitly)
   - otherwise list and update the smallest current owner named by
     `.agents/references/source_order.md`; never add facts to retired migration
     journals
4. Use absolute dates in prose ("2026-05-07", not "Thursday").
5. Mention staged scope or commit scope when the worktree was dirty.
6. Run `make check-agent-memory` and report any failures.
