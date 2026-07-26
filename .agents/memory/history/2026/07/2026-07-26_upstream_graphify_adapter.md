---
id: 2026-07-26_upstream_graphify_adapter
date: 2026-07-26
title: "Upstream Graphify Adapter"
status: done
topics: [graphify, adapter, scaffold, g005]
confidence: high
canonical_updates_needed: []
---

# Upstream Graphify Adapter

## Outcome

G005 removed the custom Graphify schema, query, report, pending-state, and
freshness wrappers. Pinned upstream Graphify retains native schema, clustering,
report, `query`, `path`, `explain`, `tree`, and merge behavior. The repository
keeps only a deterministic adapter, explicit bridge, history enforcement, and
the `S -> G` source-then-graph commit policy. `.graphifyignore` was deleted;
source admission is now explicit and independent of ignore-file behavior.

Raw native Typst and TeX extraction produced zero nodes, so the retained bridge
converts only explicit Typst, TeX, and Bib structure into Python AST input. It
maps every generated node and link back to the exact authoritative source and
line, including draft/status, symbol, equation, glossary, citation, paper, and
code relationships. Custom NER and agent-learned edges were rejected as
nondeterministic, non-authoritative graph invention.

## Corpus and Generation

The adapter admits exactly three source families and generated 695 sources:
227 production-code Python files under `aria_nbv/aria_nbv`, 97 active thesis
and shared Typst/Bib files, and 371 literature-manifest or selected TeX files.
All other paths are excluded, including package tests, scripts, configuration,
scaffold/operator guidance, AGENTS and skills, OMX state, debriefs, transcripts,
and unselected documentation or literature sources.

An in-memory production run with Graphify 0.9.22 generated 11,112 nodes and
20,214 links. Native artifacts contained no temporary corpus paths.

## Scope and Decisions

The accepted production integration count fell from 1,959 to 1,242 LOC. The
baseline count covers five custom Python wrappers (1,878 lines) plus the old
81-line Graphify-specific post-commit hook. The retained 1,242-line core is
`graphify_adapter.py` (640), `graphify_bridge.py` (403), and
`check_graphify_history.py` (199). For like-for-like accounting, including the
current generic 44-line post-commit dispatcher gives 1,959 to 1,286 lines; the
dispatcher is excluded from the retained core count because it is hook glue.

The semantic bridge path was not available because its credentials were
unavailable. Broad agent slices proved too large and were split into bounded
corpus, upstream-command, merge, adapter/bridge, and integration slices.

## TODO Disposition

Measured-autoresearch mixed-iteration guidance and skill/domain-truth cleanup
are explicitly deferred to G006. Graph visualization and the full independent
gates are deferred to G007. No unresolved inline G005 TODO remains.

## Validation

- In-memory production generation reproduced 695 sources, 11,112 nodes,
  20,214 links, exact source/line validation, and zero temporary paths.
- Adapter and bridge pytest suite: 21 passed.
- Graph history and post-commit dispatch fixtures passed.
- WP7 integration budget self-test passed.
- Ruff check and format-check passed for the retained Python core.
- The focused G005 surfaces contain no `TODO`, `FIXME`, or `HACK` markers.

Graphify remains source-derived navigation. Exact code, active Typst and Bib
sources, and exact external papers remain authoritative.
