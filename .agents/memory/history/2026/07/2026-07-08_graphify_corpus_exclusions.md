---
id: 2026-07-08_graphify_corpus_exclusions
date: 2026-07-08
title: "Graphify Corpus Exclusions"
status: done
topics: [graphify, navigation, corpus-policy]
confidence: high
canonical_updates_needed: []
files_touched:
  - path: .graphifyignore
    kind: corpus-policy
  - path: AGENTS.md
    kind: guidance
artifacts:
  - graphify-out/graph.json
  - graphify-out/GRAPH_REPORT.md
  - graphify-out/graph.html
---

## Task

Narrow the Graphify root corpus by excluding `.codex`, `.agents/skills`,
`.configs`, root `scripts`, `AGENTS.md`, `aria_nbv/scripts`, and
`aria_nbv/tests`. The requested `.agent/skills` path was also added as a
compatibility exclusion alongside the actual `.agents/skills` path.

## Method

Removed the previous `.graphifyignore` reincludes for the excluded surfaces and
added explicit final exclusions so they still win after broad directory
reincludes. Updated root guidance to describe the narrower corpus as package
code, docs, and important `.agents` references/memory/backlog, with the new
exclusions called out.

Rebuilt the local generated graph from the narrowed detector output. The rebuild
used current AST extraction plus semantic cache hits only; uncached non-code
files were not sent through another Codex extraction pass for this narrow
policy edit.

## Outputs

The detector now reports 295 supported files and about 500k words: 199 code, 65
document, 7 paper, and 24 image files. The rebuilt graph has 5,279 nodes,
13,315 edges, and 161 communities. `graphify-out/graph.html` is an aggregated
community view because the graph remains above the node-level HTML limit.

Verification found zero graph nodes sourced from `AGENTS.md`, `.codex/`,
`.configs/`, root `scripts/`, `aria_nbv/scripts/`, `aria_nbv/tests/`,
`.agents/skills/`, or `.agent/skills/`.

## Verification

- Graphify detector summary from `graphify.detect.detect(Path("."))`
- `graphify diagnose multigraph --graph graphify-out/graph.json --max-examples 5`
- `graphify query "How do target RRI, VIN, and rollout storage connect?" --budget 1200`
- direct `graphify-out/graph.json` source-file scan for excluded prefixes
