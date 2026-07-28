# Agent Memory

This directory replaces the old flat `.codex/*.md` note bucket.

## Layout
- `state/`: legacy journals awaiting claim-level PR2 disposition; supporting
  migration evidence only
- `history/YYYY/MM/`: dated task debriefs and imported episodic notes
- `index/`: migration manifests and machine-oriented indexes

## What Happened To The Old `.codex/*` Debriefs
- Dated or clearly episodic notes were imported into `history/YYYY/MM/` with YAML frontmatter.
- Ambiguous or undated legacy notes were archived under `archive/codex-legacy/flat/`.
- Previous canonical-input documents such as the old `AGENTS.md` and `AGENTS_INTERNAL_DB.md` were archived under `archive/codex-legacy/canonical-inputs/`.
- The migration inventory is recorded in `index/codex_migration_manifest.md`.

## Current Policy
- Non-trivial tasks should leave a debrief in `history/YYYY/MM/`.
- If a task changes current truth, update the smallest owner named by
  `.agents/references/source_order.md`; do not add facts to `state/`.
- Extracted proposal, transcript, or review requirements belong in the agents DB
  when actionable and in `history/` when they are task debriefs. Promotion to a
  current owner requires source-backed review.
- If a task does not change current truth, say so explicitly in the debrief instead of silently relying on chat history.
