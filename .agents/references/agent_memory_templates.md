# Agent Memory Templates

Use these templates for native debriefs under `.agents/memory/history/YYYY/MM/`.

`canonical_updates_needed` preserves the debrief workflow name but lists only
exact existing owner paths: package code/guidance, thesis/docs, references, or
agents-DB files. It never targets a generic current-state journal.

Existing records with `status: legacy-imported` are grandfathered archive evidence and do not need to be backfilled unless a task explicitly asks for it.

## Required Frontmatter
- `id`
- `date`
- `title`
- `status`
- `topics`
- `confidence`
- `canonical_updates_needed`

Use absolute ISO dates (`2026-05-08`) in both frontmatter and prose; never
relative dates ("Thursday", "yesterday", "last week"). Debriefs outlive the
session that wrote them. Use `make new-debrief TITLE='...'` to scaffold a
file with today's absolute date pre-filled.

## Native Debrief With No Canonical Updates

```yaml
---
id: 2026-03-25_example_debrief
date: 2026-03-25
title: "Example Debrief"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed: []
---
```

## Native Debrief With Canonical Updates

```yaml
---
id: 2026-03-25_example_with_state_updates
date: 2026-03-25
title: "Example Debrief With State Updates"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed:
  - docs/contents/thesis/questions.qmd
  - .agents/todos.toml
---
```

## Optional Fields
- `files_touched`
- `source_legacy_path`
- `artifacts`
- `assumptions`

Keep the body concise:
- task
- method or commands
- findings or outputs
- verification
- canonical state impact

Useful additions when they materially clarify the work:
- mention staged scope or commit scope when the worktree was dirty
- note whether compatibility was preserved deliberately or removed deliberately
