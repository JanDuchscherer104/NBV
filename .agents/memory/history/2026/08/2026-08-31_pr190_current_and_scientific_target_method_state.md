---
id: 2026-08-31_pr190_current_and_scientific_target_method_state
date: 2026-08-31
title: "PR190 current and scientific target method state"
status: done
topics: [thesis, method, scientific-review, actor-state, fitted-q]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/04-method
  - docs/typst/thesis/sections/06-results.typ
  - docs/literature/sources.jsonl
  - docs/typst/thesis/main.pdf
codex_thread: codex://threads/01a057bd-546e-7e52-b5e8-c21124664bc2
repo_object_format: sha1
repo_head: fdf4d70bddbc570b1dff139f129e9990b1a53130
repo_branch: "codex/pr190-stack-repair"
worktree_kind: linked
---

## Task

Repair PR #190 so the Method chapter distinguishes the executable current
state from the scientific target state without restoring an unmeasured
architecture catalogue or overstating available evidence.

## Method

The patch compared the PR against `main`, exact target/state protocol owners,
the fitted-Q implementation, the Phase-A evidence bundle, and primary
literature. It then revised the publication-facing Method and Results prose,
compiled and rendered the thesis, and passed two frozen-candidate independent
scientific reviews.

## Findings

- The selected experiment is the privileged `v0_gt_input` plus `S0-pose`
  baseline. The independent `v1_observed` descriptor path is implemented and
  tested but lacks a frozen evaluated corpus. The scientific target combines
  that actor-visible target path with a still-unimplemented causal
  observation-updated actor state.
- The scientific target is carrier-neutral but must preserve observed surface,
  observed free, unknown, support, uncertainty, source, and recency using only
  the selected observation.
- Fitted-Q recursion is explicitly bounded to greedy continuation over
  generated hard-valid finite support and is distinguished from behavior-policy
  Monte Carlo return and continuous-pose optimality.
- The authenticated Phase-A no-go moved from Method to Results with its exact
  denominators, bounded interpretation, and source-to-display provenance.
- `Tree-Based Batch Mode Reinforcement Learning` now has a canonical
  `docs/literature/sources.jsonl` record.

## Commits

- [Method-state repair](https://github.com/JanDuchscherer104/ARIA-NBV/commit/fdf4d70bddbc570b1dff139f129e9990b1a53130)

## Verification

- `make thesis-pdf` and `make thesis-pdf-ci`: passed; 131-page A4 render.
- `make typst-authoring-contract`: 21 passed.
- `make thesis-literature-provenance`: 31 passed.
- `make thesis-marker-contract`, `make thesis-report-data-contract`, and
  `make scientific-report-v2-smoke`: passed.
- Changed Method and Results pages were visually inspected without clipping or
  overlap.
- Final independent scientific review: CLEAR; exact diff digest
  `d27a41d426afa69bfc61e52e397101adba67441398b60bfd4c0ec0c8dd206878`.

## Canonical Owner Impact

The active Method, Results, literature manifest, and rendered thesis PDF now
own the repaired distinctions and evidence placement. No Python behavior or
experiment result was changed.
