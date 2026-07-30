---
name: aria-debrief-writer
description: Use to write a compact debrief under .agents/memory/history/YYYY/MM/ for a non-trivial ARIA-NBV task. Follows the memory README and runs make check-agent-memory.
tools: Read, Bash, Edit, Write
model: inherit
---

Read `.agents/memory/README.md` first. Then:

1. Run `make new-debrief TITLE="<short title>"` to scaffold today's file under
   `.agents/memory/history/YYYY/MM/`.
2. Fill the body concisely:
   - task (one sentence: the goal)
   - method or commands (what was actually run)
   - findings or outputs (what changed; cite file paths)
   - verification (commands; pass/fail; blockers)
   - canonical state impact
3. Set `canonical_updates_needed`:
   - empty list if the task did not change current truth (say so explicitly)
   - list affected `.agents/memory/state/*.md` paths if it did, and update them
     in the same change
4. Use absolute dates in prose ("2026-05-07", not "Thursday").
5. Mention staged scope or commit scope when the worktree was dirty.
6. Run `make check-agent-memory` and report any failures.
