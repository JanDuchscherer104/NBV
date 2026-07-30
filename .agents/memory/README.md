# Agent Memory

This directory replaces the old flat `.codex/*.md` note bucket.

## Layout
- `state/`: canonical current truth that should stay small and current
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes

## What Happened To The Old `.codex/*` Debriefs
- Dated or clearly episodic notes were imported into `history/YYYY/MM/` with YAML frontmatter.
- Ambiguous or undated legacy notes were archived under `archive/codex-legacy/flat/`.
- Previous canonical-input documents such as the old `AGENTS.md` and `AGENTS_INTERNAL_DB.md` were archived under `archive/codex-legacy/canonical-inputs/`.
- The migration inventory is recorded in `index/codex_migration_manifest.md`.

## Current Policy
- Non-trivial tasks should leave a debrief in `history/YYYY/MM/`.
- If a task changes current truth, update one or more files in `state/`.
- Extracted proposal, transcript, or review requirements belong in `state/` only
  when they change durable truth, in the agents DB when they are actionable, and
  in `history/` when they are task debriefs.
- If a task does not change current truth, say so explicitly in the debrief instead of silently relying on chat history.

## Debrief Contract

Native debriefs use absolute ISO dates and include `id`, `date`, `title`,
`status`, `topics`, `confidence`, and `canonical_updates_needed`. Use
`make new-debrief TITLE="..."` to create the canonical frontmatter and body.
Keep the body to task, method, findings, verification, and canonical-state
impact. Add `files_touched`, `source_legacy_path`, `artifacts`, or assumptions
only when they make the record materially easier to audit.

Existing records with `status: legacy-imported` are grandfathered archive
evidence and do not need backfilling unless a task explicitly requests it.
Use absolute ISO dates (`2026-05-08`) in frontmatter and prose; debriefs outlive
the session that wrote them.

### No Canonical Updates

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

### With Canonical Updates

```yaml
---
id: 2026-03-25_example_with_state_updates
date: 2026-03-25
title: "Example Debrief With State Updates"
status: done
topics: [scaffold, codex, memory]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/DECISIONS.md
  - .agents/memory/state/PROJECT_STATE.md
---
```

When it materially clarifies the work, note staged or commit scope in a dirty
worktree and whether compatibility was deliberately preserved or removed.
