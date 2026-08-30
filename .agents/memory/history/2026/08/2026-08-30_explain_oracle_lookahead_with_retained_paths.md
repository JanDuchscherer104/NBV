---
id: 2026-08-30_explain_oracle_lookahead_with_retained_paths
date: 2026-08-30
title: "Explain Oracle Lookahead With Retained Paths"
status: done
topics: [thesis, figures, typst, cetz, rollouts, scientific-review]
confidence: high
canonical_updates_needed: []
touched_owner_paths: [docs/typst/thesis/figures/oracle_lookahead_tree.typ, docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ]
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: 8e709383462e0ef00e106c21b898f9bf34b9271c
repo_branch: "codex/thesis-figure-oracle-lookahead-geometry"
worktree_kind: linked
---

## Task
Replace the generic oracle-lookahead box hierarchy with a clean path-native
figure that explains immediate-versus-finite-horizon ordering without
conflating invalidity, branch-factor omission, beam pruning, or persistence.

## Method
Audited the exact rollout engine, state, recipe, equation, and thesis owners;
queried current CeTZ and Typst guidance through Context7; preserved parent-page
baselines; iterated standalone and final-page color/grayscale renders; and
patched every valid independent scientific-review finding before publication.

## Findings
The Fletcher baseline emphasized state boxes and made the non-myopic insight a
detached textual conclusion. The replacement
`docs/typst/thesis/figures/oracle_lookahead_tree.typ` uses one factual prefix,
two complete beam-retained paths across explicit time planes, and a ring to
mark the highest-ranked retained path. A dotted cross terminates an invalid row.
A single-bar dashed stub denotes a valid row outside branch factor two that
remains in the full candidate shell; a double-bar dashed stub denotes an
expanded path removed by beam width two. The chapter owner now states that the
highest-ranked chain's first action can differ from one-step greedy, while both
solid paths persist. Its caption and alternative text scope the constructed
ordering to target-root gain at `h=2`, `gamma=1` and explicitly reject measured
or learned-policy interpretations.

## Commits
- [c9ced24f2037376539f16f9c7cccc1fd33393f63](https://github.com/JanDuchscherer104/ARIA-NBV/commit/c9ced24f2037376539f16f9c7cccc1fd33393f63)

## Verification
- standalone CeTZ 0.5.2 compile: pass, one `160 x 72 mm` page
- `make thesis-pdf` and `make thesis-pdf-ci`: pass, 122 A4 pages
- `make typst-authoring-contract thesis-marker-contract`: pass
- final physical page 65 color/grayscale inspection: pass
- targeted branch/beam rollout test: pass
- independent visual review: PASS, zero P0--P2
- independent verifier: PASS, pixel-identical fresh renders and zero P0--P2
- independent scientific re-review after two valid P2 corrections:
  APPROVE/CLEAN, zero P0--P2
- `git diff --check`: pass

## Canonical Owner Impact
`docs/typst/thesis/figures/oracle_lookahead_tree.typ` remains the vector figure
owner. `03-02-target-task-and-rri-labels.typ` remains the prose, caption,
alternative-text, and interpretation owner. The Python rollout engine and
shared equations were verified but not changed.
