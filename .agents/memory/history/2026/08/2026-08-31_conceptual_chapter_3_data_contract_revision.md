---
id: 2026-08-31_conceptual_chapter_3_data_contract_revision
date: 2026-08-31
title: "Conceptual Chapter 3 data-contract revision"
status: done
topics: [thesis, data-contracts, typst, scientific-writing, pr-189]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - .agents/skills/typst-authoring/references/figures-tables.md
  - docs/typst/shared/tables.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation
  - scripts/tests/test_typst_authoring_hygiene.py
codex_thread: codex://threads/01a057bd-546e-7e52-b5e8-c21124664bc2
repo_object_format: sha1
repo_head: 189018eeed94163c11bdd5cfa2e4d05db3b2929d
repo_branch: "codex/pr189-conceptual-prose"
worktree_kind: linked
---

## Task
Revise every Chapter 3 section changed by PR #189 so that it explains the
mathematical data contracts of generation, replay, and storage with positive,
scientifically relevant definitions, while addressing all open review comments.

## Method
Compared the PR branch with `origin/main`, mapped the chapter around information,
action-support, measurement, and storage contracts, reused the shared thesis
symbols and equations, and rendered pages 50--73 for visual inspection. Updated
the shared table constructor and authoring rule so authored row structure matches
the rendered matrix structure.

## Findings
Chapter 3 now presents a typed transformation from logged information state to
target task, finite candidate support, oracle-labelled factual chains, and
normalized replay relations. Actor/oracle information roles, feasibility versus
utility, candidate-support populations, measurement constructs, and missingness
predicates are explicit. The storage section describes each relation by its
mathematical role and scientific purpose instead of contrasting it with objects
that are absent.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/189018eeed94163c11bdd5cfa2e4d05db3b2929d

## Candidate Owner Intent
<!-- Omit this section unless the agent-behavior candidate-intent branch applies. -->
- Statement: Explain a scientific object positively through its structure, role,
  and justification; avoid using comparisons to what it is not as the primary
  explanation.
- Evidence: Direct review feedback on PR #189 identified repeated "rather than"
  and "remain" constructions as compressed, perspective-free prose.
- Scope and target owner: Thesis exposition; candidate target
  `.agents/skills/academic-writing/references/reader-centred-exposition.md`.
- Status: proposed for current-user review

## Verification
Passed `make typst-authoring-contract` (21 tests), strict Typst hygiene for the
Chapter 3 directory, `make thesis-marker-contract`,
`make thesis-literature-provenance` (31 tests), `make thesis-pdf-ci`, the
Typst-authoring skill validator, `git diff --check`, and a visual inspection of
rendered thesis pages 50--73.

## Canonical Owner Impact
The Chapter 3 Typst sources own the revised scientific exposition. The shared
table constructor, its authoring reference, and its inventory regression test
own the new source-layout contract. No further canonical updates are needed.
