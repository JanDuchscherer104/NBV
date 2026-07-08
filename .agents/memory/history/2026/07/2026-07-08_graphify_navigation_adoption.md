---
id: 2026-07-08_graphify_navigation_adoption
date: 2026-07-08
title: "Graphify Navigation Adoption"
status: done
topics: [graphify, navigation, litkg, agent-guidance]
confidence: high
canonical_updates_needed: []
files_touched:
  - path: AGENTS.md
    kind: guidance
  - path: .graphifyignore
    kind: corpus-policy
  - path: .gitignore
    kind: generated-artifact-policy
  - path: .agents/references/omx_quick_reference.md
    kind: guidance
  - path: scripts/validate_agent_memory.py
    kind: validator
  - path: scripts/git_hooks/post-commit
    kind: hook
artifacts:
  - graphify-out/graph.json
  - graphify-out/GRAPH_REPORT.md
  - graphify-out/graph.html
---

## Task

Adopt Graphify as the default ARIA-NBV navigation graph while preserving
`litkg-rs` as the source-authority and claim-check layer.

## Method

Added a repo-owned `.graphifyignore` so `graphify .` indexes the package, docs,
important agent guidance/state/backlog surfaces, scripts, `AGENTS.md`, core KG
config, and the vendored `.codex/skills/graphify/**` skill while excluding
operator state, external repos, generated docs/sites, caches, large media, and
`graphify-out/`.

Updated root guidance to query `graphify-out/graph.json` first for architecture
and file-relationship questions, with `litkg-rs` retained for `kg-search`,
`kg-route`, `kg-claim-check`, Semantic Scholar/literature enrichment, and
thesis/advisor evidence. Updated the OMX quick reference and memory validator
so `.codex/skills/graphify/**` is the only approved checked-in `.codex/*.md`
project-skill exception.

Built the first graph in normal mode: AST extraction for code plus Codex-backed
semantic extraction for the first six text chunks. SVG/image chunks were
deferred. Installed Graphify hooks after repairing the local `.git/config`
duplicate `github-pr-owner-number` entry.

## Outputs

The curated detector baseline is 488 files and about 604k words: 352 code, 105
document, 7 paper, and 24 image files. The current graph has 8,060 nodes,
18,221 edges, and 549 communities. `graphify-out/graph.html` is an aggregated
community visualization because the graph is above the node-level HTML limit.

`graphify query "How do target RRI, VIN, and rollout storage connect?"`
returns the expected VIN, rollout Zarr, offline dataset, and RRI nodes. The
direct shortest-path query from `target-specific RRI` to `Q_H` remains
ambiguous and returns no path; the narrower query
`target-specific RRI Q_H` with `conceptually_related_to` surfaces `Q_H Tensor
View`, `Q_H Training-Hot View`, `RriOrdinalBinner`, and `.target()`.

## Verification

- `graphify --help`
- `graphify diagnose multigraph --graph graphify-out/graph.json --max-examples 5`
- `graphify hook status`
- `graphify update .`
- `make check-agent-memory`
- `make kg-status`
- `make kg-claim-check KG_CLAIM="ARIA-NBV keeps Graphify as a navigation graph while litkg-rs remains the authority layer for source-backed kg-search and kg-claim-check workflows."`
- `aria_nbv/.venv/bin/ruff check scripts/validate_agent_memory.py`
- `python3 -m py_compile scripts/validate_agent_memory.py`
- `git diff --check`
