---
id: 2026-08-26_conditional_q_and_scalar_horizon_thesis_clarification
date: 2026-08-26
title: "Conditional Q and scalar horizon thesis clarification"
status: done
topics: [thesis, qh, finite-horizon, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/shared/glossary.typ
  - docs/typst/shared/equations.typ
  - docs/typst/shared/equations/model.typ
  - docs/typst/thesis/sections/04-method/04-02-descriptor-and-encoding-plan.typ
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
  - docs/typst/thesis/sections/04-method/index.typ
codex_thread: codex://threads/01a03ce8-e3f0-72e2-821a-7a2fe03d5e35
repo_object_format: sha1
repo_head: 57b796130aa0490621fc928bd52d31b9ec0287eb
repo_branch: "codex/conditional-q-horizon-thesis-followup"
worktree_kind: linked
---

## Task
Realize the accepted conceptual explanation of conditional Q and scalar requested-horizon semantics in the active thesis owners.

## Method
Reused the canonical shared equations and symbols, expanded their interpretation in the active descriptor and finite-value Method sections, synchronized the Q_H glossary entry and Method synopsis, and corrected the A1 equation to show separate normalized budget and requested-horizon encodings. The patch was transplanted onto PR #145's exact head and resolved against its A1-only architecture surface without importing the later PR #131--138 stack.

## Findings
Conditional Q now explicitly conditions the first action while remaining indexed by target and requested horizon; it is not a validity probability or a feasibility-weighted score. The Method distinguishes the triangular syntactic domain from empirical horizon support, names h=b_t as the full-budget diagonal, explains h<b_t off-diagonal queries and Q_0=0, and separates horizon choice from represented-state sufficiency. It also records why authoritative hard masking must remain outside the scorer, including the negative-Q failure of zero-filled invalid rows.

## Commits
- [57b796130aa0490621fc928bd52d31b9ec0287eb](https://github.com/JanDuchscherer104/ARIA-NBV/commit/57b796130aa0490621fc928bd52d31b9ec0287eb)

## Verification
- `make typst-authoring-contract thesis-pdf-ci PYTHON_INTERPRETER=/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/python` passed.
- Six focused VIN tests for requested horizons, fail-closed bounds, feasibility independence, and action-mask independence passed on the PR #145-based branch.
- Rendered thesis pages 49 and 61--64 were visually inspected; equations, sets, page flow, and prose remained legible.
- The isolated worktree had no local `.venv`; verification used the existing package environment while importing this worktree's sources.

## Canonical Owner Impact
The active Method synopsis, descriptor/interface section, finite-horizon value-model section, shared A1 equation, and Q_H glossary owner now agree on conditionality, diagonal/off-diagonal horizon semantics, separate budget/horizon encoding, state aliasing, feasibility separation, and hard-mask ownership. No Python behavior changed.
