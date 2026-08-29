---
id: 2026-08-30_actor_oracle_boundary_figure
date: 2026-08-30
title: "actor oracle boundary figure"
status: done
topics: [thesis, figures, typst, qh, scientific-review]
confidence: high
canonical_updates_needed: []
touched_owner_paths: [docs/typst/thesis/figures/actor_oracle_boundary.typ, docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ]
codex_thread: codex://threads/01a04f6f-b0ec-7073-9d78-9dd125d8436b
repo_object_format: sha1
repo_head: a6cde270a03d4337e0798ed6f3e89209425a3c76
repo_branch: "codex/thesis-figure-actor-oracle-boundary"
worktree_kind: linked
---

## Task
Revise the actor/oracle figure so its topology makes decision-time legality,
mask independence, and post-prediction supervision unambiguous.

## Method
Preserved standalone and A4-page baselines, reviewed the exact adjacent thesis
claims and canonical Q_H owners, queried Fletcher and Typst guidance through
Context7, iterated page-sized color/grayscale renders, and patched every valid
independent scientific-review finding before publication.

## Findings
The previous dashed oracle path visually terminated at the scorer, while reason
codes appeared inside a scorer-bound candidate table. The revised
`actor_oracle_boundary.typ` separates actor inference from privileged target
generation, emits one raw conditional value per materialized row, applies the
hard mask only downstream, and branches reason codes to audit. The integration
owner now supplies a shorter complementary caption and detailed alternative
text. PR review further narrowed candidate renders to the compact hard-valid
subset, preserving the contrast with scorer outputs for all materialized rows.

## Commits
- [a6cde270a03d4337e0798ed6f3e89209425a3c76](https://github.com/JanDuchscherer104/ARIA-NBV/commit/a6cde270a03d4337e0798ed6f3e89209425a3c76)
- [ab48be5c5f9ac84ad93e6d75ddeaae31dbe1a649](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ab48be5c5f9ac84ad93e6d75ddeaae31dbe1a649)

## Verification
- standalone Typst compile: pass
- `make thesis-pdf` and `make thesis-pdf-ci`: pass, 121 A4 pages
- `make typst-authoring-contract thesis-marker-contract`: pass
- final page 19 color/grayscale visual inspection: pass
- independent scientific review of tree
  `affa517d29a113751d5f6ac2eecba288211d9412`: APPROVE/CLEAN, zero P0--P2
- independent review of the hard-valid-render correction at tree
  `91bbdfe18b02186ea2ab44e423c70760af5a20e1`: APPROVE/CLEAN
- `git diff --check`: pass

## Canonical Owner Impact
`docs/typst/thesis/figures/actor_oracle_boundary.typ` remains the figure owner;
`03-01-state-and-visibility.typ` remains the caption, alternative-text, and
interpretation owner. No Python, configuration, equation, or symbol owner
changed.
