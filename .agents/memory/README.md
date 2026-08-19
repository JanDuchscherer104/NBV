# Agent Memory

This directory stores episodic evidence and migration indexes. Current truth
lives with the smallest source-order owner: active Typst, Python/configuration,
tests, setup, or agent guidance. The agents DB stores actionable follow-up
metadata; it is not a narrative owner.

## Layout
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes

## What Happened To The Old `.codex/*` Debriefs
- Dated or clearly episodic notes were imported into `history/YYYY/MM/` with YAML frontmatter.
- Ambiguous or undated legacy notes were archived under `archive/codex-legacy/flat/`.
- Previous canonical-input documents such as the old `AGENTS.md` and `AGENTS_INTERNAL_DB.md` were archived under `archive/codex-legacy/canonical-inputs/`.
- The migration inventory is recorded in `index/codex_migration_manifest.md`.

## Current Policy
- Non-trivial tasks should leave a debrief in `history/YYYY/MM/`.
- If a task changes current truth, update its exact canonical owner selected by
  `.agents/skills/aria-nbv-context/SKILL.md#owner-hierarchy`.
- Architect and critic review outputs remain session-local. Capture only their
  accepted durable decisions in the relevant Typst, code/config/test, setup, or
  guidance owner; put actionable work in the agents DB and a bounded task
  summary in `history/`.
- If a task does not change current truth, say so explicitly in the debrief instead of silently relying on chat history.

## Debrief Contract

Native debriefs use absolute ISO dates and include `id`, `date`, `title`,
`status`, `topics`, `confidence`, `canonical_updates_needed`, and the
originating Codex thread as `codex_thread: codex://threads/<thread-id>`. Use
`make new-debrief TITLE="..." CODEX_THREAD_ID="<thread-id>"` to create the
canonical frontmatter and body. Existing historical records are grandfathered.
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
codex_thread: codex://threads/<thread-id>
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
  - docs/typst/thesis/development/roadmap.typ
  - aria_nbv/aria_nbv/<owner>.py
codex_thread: codex://threads/<thread-id>
---
```

When it materially clarifies the work, note staged or commit scope in a dirty
worktree and whether compatibility was deliberately preserved or removed.
