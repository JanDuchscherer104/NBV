# Agent Memory

This directory replaces the old flat `.codex/*.md` note bucket.

## Layout
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes
- `transcripts/`: reviewed or raw transcript evidence with non-authoritative
  trust tiers

## What Happened To The Old `.codex/*` Debriefs
- Dated or clearly episodic notes were imported into `history/YYYY/MM/` with YAML frontmatter.
- Ambiguous or undated legacy notes were archived under `archive/codex-legacy/flat/`.
- Previous canonical-input documents such as the old `AGENTS.md` and `AGENTS_INTERNAL_DB.md` were archived under `archive/codex-legacy/canonical-inputs/`.
- The migration inventory is recorded in `index/codex_migration_manifest.md`.

## Current Policy
- Non-trivial tasks should leave a debrief in `history/YYYY/MM/`.
- If a task changes a durable fact, update the exact thesis, package, test,
  docstring, reference, or backlog owner named by source order.
- Extracted proposal, transcript, or review requirements belong in the agents DB
  when actionable and in `history/` or `transcripts/` when they are episodic
  evidence. They do not become current truth without an exact owner edit.
- If a task does not change current truth, say so explicitly in the debrief instead of silently relying on chat history.
