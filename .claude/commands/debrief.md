---
description: Scaffold a new dated debrief under .agents/memory/history/YYYY/MM/.
allowed-tools: Bash(make new-debrief:*), Read, Edit
argument-hint: "<short title>"
---

Run `make new-debrief TITLE="$ARGUMENTS"` to scaffold the file with valid
frontmatter (today's absolute date, empty `canonical_updates_needed`, required
keys per `.agents/memory/README.md`).

Then open the file and fill in:
- task (one sentence: what was the goal)
- method or commands (what was actually run)
- findings or outputs (what changed; cite file paths)
- verification (commands that ran; pass/fail; blockers)
- canonical state impact (set `canonical_updates_needed` or say "none" explicitly)

Keep the body short. If the work changed durable truth, list the affected
`.agents/memory/state/*.md` files in `canonical_updates_needed` and update them
in the same change.
