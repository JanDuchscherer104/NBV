# Agent Memory

This directory replaces the old flat `.codex/*.md` note bucket.

## Layout
- `state/`: canonical current truth that should stay small and current
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes
- `transcripts/commits/YYYY/MM/`: redacted, non-authoritative conversation
  slices linked to explicitly Codex-authored commits

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
- Raw/full Codex sessions stay in the user-local session store. Commit slices
  omit raw identifiers and machine/session paths. Each capture requires an
  explicit UTC scope start and excludes earlier messages, including earlier
  same-repository discussion in the same session. The canonical scope boundary
  is hash-bound with the snapshot identity. System, developer, tool, and custom
  records remain represented only by the snapshot hash. For eligible
  user/assistant messages, balanced runtime-wrapper blocks are stripped before
  credential/path sanitization; a remaining malformed runtime tag excludes the
  whole message, and final artifacts reject every residual runtime tag. This is
  not a guarantee of arbitrary semantic PII detection.
  Slices support provenance review only; durable decisions still require
  promotion into their owning source.
- The tracked legacy transcript files outside `transcripts/commits/` are
  grandfathered historical evidence. Do not rewrite them into commit slices or
  use them as the template for new artifacts.
- Normal and synthetic merge commits only inherit unchanged parent slices.
  Authored slices bind their expected parent and complete non-transcript tree,
  so replay or content changes require recapture. Active merge commits are not
  an authoring surface, and artifact filesystem operations fail closed on
  symlinked or concurrently replaced parent directories.
  Squash merging multiple transcript-bearing commits is not directly supported:
  the resulting single-parent commit must instead carry exactly one newly
  captured slice and matching trailer.

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
