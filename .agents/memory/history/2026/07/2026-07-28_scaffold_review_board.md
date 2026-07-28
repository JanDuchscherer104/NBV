---
id: 2026-07-28_scaffold_review_board
date: 2026-07-28
title: "Private Scaffold Review Board"
status: done
topics: [scaffold, agents-db, omx, graphify, review]
confidence: high
canonical_updates_needed: []
files_touched:
  - scripts/scaffold_review.py
  - scripts/tests/test_scaffold_review.py
  - .agents/references/scaffold_review.md
  - .agents/refactors.toml
  - Makefile
---

## Task

Provide a simple interactive way to review scaffold intent, selected OMX goals,
active Agents DB records, scaffold ownership surfaces, and live PR #30 facts.

## Result

Added one standard-library generator that produces an ignored, self-contained
HTML board and local Quarto wrapper. Each item accepts `yes`, `no`, or a revised
statement; browser-local decisions can be exported as JSON. The board reads
existing owners but never mutates Agents DB or canonical human intent.

Amended `refactor-016` instead of creating duplicate backlog records. PR #30 is
recorded as a 383-file reviewability problem whose useful changes should be
extracted into small owner-scoped PRs. LitKG retirement remains an explicit
capability decision rather than dead-code cleanup.

## Verification

- Focused tests, Ruff, and mypy passed.
- Agents DB validation passed.
- Direct HTML and local Quarto renders succeeded.
- Headless Chrome verified desktop and mobile rendering.
- The broader memory validator still reports three pre-existing `origin/main`
  failures: one stale advisor-deck path and two OMX plans without frontmatter.
