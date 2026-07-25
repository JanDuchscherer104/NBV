---
id: 2026-07-26_graphify_corpus_narrowing
date: 2026-07-26
title: "Graphify Corpus Narrowing"
status: done
topics: [graphify, corpus, scaffold, progressive-disclosure]
confidence: high
canonical_updates_needed: []
---

## Task

Narrow the canonical Graphify corpus to exactly three source families without
replacing extraction/schema behavior or implementing the Typst/TeX bridge.

## Outcome

The fresh corpus contains 728 sources under only the `aria_nbv` and `docs`
top-level roots: 239 production-code sources from `aria_nbv/aria_nbv`, 115
active thesis/shared sources from `docs/typst/{thesis,shared}`, and 374
literature sources from `docs/literature/sources.jsonl` plus its 35 selected
TeX source families. Config, scaffold/operator, AGENTS/skills, test, script,
OMX, debrief, and transcript paths are outside graph nodes. The implementation
and test diff was net-negative by 224 lines; no commit was created and transcript
exports were not touched.

Graphify remains source-derived navigation, not project truth. Claims still
resolve to exact production code, active Typst thesis/shared sources, and the
selected literature sources.

## Verification

- `python scripts/tests/test_graphify_freshness.py` — passed, including stale
  partition fallback and fresh three-family fixtures.
- `python scripts/tests/test_graphify_history.py` — passed, including excluded
  operator changes and thesis/literature corpus changes.
- `python scripts/tests/test_graphify_integration.py` — passed.
- `python scripts/check_graphify_freshness.py` — passed; all three partitions
  and bridge revisions were fresh.
- Ruff formatting and checks passed for the touched Graphify Python surfaces.

## Canonical State Impact

The corpus policy, concise Graphify guidance, focused contract tests, and three
canonical graph artifacts already record the completed narrowing. No further
canonical updates are needed.
