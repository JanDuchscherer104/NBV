---
id: 2026-08-01_graphify_deep_native_codex_refresh
date: 2026-08-01
title: "Graphify Deep Native Codex Refresh"
status: done
topics: [graphify, context, codex, knowledge-graph]
confidence: high
canonical_updates_needed: []
artifacts:
  - graphify-out/graph.json
  - graphify-out/GRAPH_REPORT.md
  - graphify-out/graph.html
  - graphify-out/graph.svg
  - graphify-out/graph.graphml
  - graphify-out/ARIA-NBV-callflow.html
  - graphify-out/GRAPH_TREE.html
  - graphify-out/wiki/
  - graphify-out/obsidian/
---

## Task

Build the ARIA projection at commit
`2ef2cf07cf8ecde0335f2db2ba1b1358173655bb`, run Graphify 0.9.31 in deep
mode using native Codex subagents only, reconcile every semantic file, and
generate the full requested export suite.

## Method

The run used the upstream Graphify skill unchanged. Both semantic cache calls
passed `mode="deep"`, and every extraction task received `DEEP_MODE=true`.
Eighteen chunks covered 387 document and paper files; incomplete first-pass
chunks were repaired before any cache write. The structural pass covered 237
code files.

## Findings

The final graph contains 6,143 nodes, 14,063 undirected edges, 20 hyperedges,
and 482 labeled communities. The health diagnostic reported 1,236 dangling
endpoint edges, one self-loop, and 1,538 undirected same-endpoint collapses;
there were no missing-endpoint edges. Native subagent token usage was not
exposed by the host interface, so Graphify's token counters remain zero rather
than an estimate.

## Verification

Semantic reconciliation covered 387 of 387 dispatched files with no outside
source files, and the saved deep cache replayed with zero misses. The manifest
stamped all 624 detected corpus files. All requested exports were non-empty,
and `python3 scripts/check_graphify_freshness.py --json` returned
`"state": "fresh"` for the commit above. During the run, another process
switched the shared checkout branch while retaining the same HEAD and added
unrelated worktree changes; those changes were preserved.

## Canonical-State Impact

No project truth changed. Graphify remains derived navigation evidence, and no
canonical state update is needed.
