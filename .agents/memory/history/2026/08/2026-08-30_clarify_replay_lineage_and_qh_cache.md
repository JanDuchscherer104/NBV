---
id: 2026-08-30_clarify_replay_lineage_and_qh_cache
date: 2026-08-30
title: "Clarify replay lineage and Q_H cache"
status: done
topics: [thesis, figures, replay, q-h, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/figures/replay_lineage_relations.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-03-replay-stores-and-diagnostics.typ
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: d7079175ecf6b64a69f01d475f239b62921aea1a
repo_branch: "codex/thesis-figure-replay-lineage-relations"
worktree_kind: linked
---

## Task

Revise the replay-lineage figure so it cleanly distinguishes persisted factual
rows from the derived padded $Q_H$ training cache without inventing schema
relations or implying that masks remove attempted candidate rows.

## Method

Mapped the figure to the replay-store and $Q_H$ reader implementation, preserved
standalone and actual-page baselines, and generated explicit professor and
student critiques. Replaced the crossing Fletcher graph with one factual
lineage rail and one separate cache-materialization relation. Regenerated and
inspected the standalone figure and physical thesis page 73 in color and
grayscale, then ran independent scientific and visual reviews against exact
hashes.

## Findings

- `source_row_id` and `target_row_id` are both stored on retained rollout rows;
  target rows do not own a persisted source foreign key.
- Retained rollouts own ordered steps, and each step owns a full candidate shell
  containing exactly one selected row.
- $Q_H$ materialization joins factual identifiers, copies and validates masks,
  and pads widths. Invalid rows remain present and auditable rather than being
  filtered out by the materialization step.
- The materialized cache is exact-checked against its factual source tables. It
  is therefore a derived training view, not an independent transition table or
  exhaustive counterfactual search tree.
- A solid left-to-right rail plus a separate downward materialization relation
  resolves the baseline edge crossings and remains readable without hue.

## Review Corrections

- Removed a false-looking Target-to-Candidate derivation crossing and enlarged
  baseline labels that fell near 5 pt at final size.
- Corrected alternative text that described the materialization arrow with the
  wrong stroke style.
- Removed an invented `source_row_id` field from the target node and made source
  and target independent parents of retained rollout rows.
- Replaced “apply masks” with “copy/validate masks” and stated that the cache
  contains copied masks.
- Regenerated stale canonical page-level review artifacts before exact re-review.
- Exact scientific and visual re-reviews approve with zero P0--P2 findings.

## Commits

- [d7079175ecf6b64a69f01d475f239b62921aea1a](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d7079175ecf6b64a69f01d475f239b62921aea1a)

## Verification

- PASS: all 105 replay-store and $Q_H$ reader tests.
- PASS: standalone Typst compile, `make thesis-pdf`, `make thesis-pdf-ci`,
  `make typst-authoring-contract`, and `make thesis-marker-contract`.
- PASS: 123-page A4 thesis; exact page 73 and standalone figure inspected in
  color and grayscale.
- PASS: independent scientific and professor/student visual re-reviews; zero
  P0--P2 findings.
- PASS: `git diff --check`.

## Canonical Owner Impact

The Typst figure owns the accepted visual explanation; the adjacent thesis
section owns its semantic alternative text, caption, and interpretive boundary.
No replay-store or reader behavior changed. Exact schema and materialization
details remain owned by implementation, tests, manifests, and reproducibility
documentation.
