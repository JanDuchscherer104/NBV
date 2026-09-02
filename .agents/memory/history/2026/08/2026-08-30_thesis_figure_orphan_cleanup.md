---
id: 2026-08-30_thesis_figure_orphan_cleanup
date: 2026-08-30
title: "thesis figure orphan cleanup"
status: done
topics: [thesis, figures, scientific-review, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths: [docs/typst/thesis/figures, .agents/todos.toml]
codex_thread: codex://threads/01a04f6f-b0ec-7073-9d78-9dd125d8436b
repo_object_format: sha1
repo_head: b966f015dbaed299c9a4d25003a0fb72283a87e5
repo_branch: "codex/thesis-figure-orphan-cleanup"
worktree_kind: linked
---

## Task
Remove complete orphaned diagram families that contradict or duplicate the
current thesis owners before improving the active conceptual figures.

## Method
Enumerated every legacy Mermaid/SVG stem and its source/render siblings, proved
zero live consumers outside the figure directory, reviewed the families against
the current actor/oracle, sampler, candidate, replay, value-model, and evidence
owners, and compared all 121 rendered thesis pages with the parent candidate.

## Findings
Eight legacy families under `docs/typst/thesis/figures/` had no compiled-thesis
consumer. Six also encoded stale or unsupported scientific contracts. Removing
all 26 source/render siblings avoids a competing truth surface while leaving the
13 active Typst-native conceptual sources and their thesis passages unchanged.
GitHub review found one active backlog pointer to the deleted sampler diagram;
`todo-092` now references the current Typst sampler-contract figure.

## Commits
- [b966f015dbaed299c9a4d25003a0fb72283a87e5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/b966f015dbaed299c9a4d25003a0fb72283a87e5)
- [e5f203fb4a820b3198c173a125eb360c83dc170e](https://github.com/JanDuchscherer104/ARIA-NBV/commit/e5f203fb4a820b3198c173a125eb360c83dc170e)

## Verification
- zero consumers for all eight stems: pass
- 121 baseline/candidate rendered page hashes: identical
- `make thesis-pdf-ci`: pass
- `make typst-authoring-contract thesis-marker-contract`: pass
- `make agents-db AGENTS_ARGS='validate'`: pass
- independent scientific review of tree
  `b0e6b87d7a1e71a3094d729b81615992fd947a5a`: APPROVE/CLEAN, zero P0--P2
- `git diff --check`: pass

## Canonical Owner Impact
No canonical scientific or Typst owner changed. The work removes only obsolete,
unconsumed source/render families from `docs/typst/thesis/figures/`; their Git
history remains recoverable. The active `todo-092` audit pointer in
`.agents/todos.toml` now targets the retained Typst contract.
