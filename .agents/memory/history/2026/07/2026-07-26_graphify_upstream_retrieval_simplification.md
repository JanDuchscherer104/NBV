---
id: 2026-07-26_graphify_upstream_retrieval_simplification
date: 2026-07-26
title: "Graphify Upstream Retrieval Simplification"
status: done
topics: [graphify, scaffold, retrieval, typst, literature]
confidence: high
canonical_updates_needed: []
---

# Graphify Upstream Retrieval Simplification

## Outcome

Graphify output is reproducible ignored local state again. The tracked graph,
generic report, merge driver, source/graph commit-pair protocol, and history
validator were removed. The integration now pins `graphifyy==0.9.26` and keeps
one adapter for corpus selection plus the Typst/TeX/Bib bridge that upstream
does not provide.

The bridge now emits direct native import and call edges for Typst symbols,
equations, glossary terms, citations, code modules, classes, and explicit
member references. Inline Typst includes and TeX include roots preserve the
thesis, appendix, and paper hierarchies. Planned references with no real owner
do not create false target nodes.

## Evidence

- Full graph: 9,799 nodes and 19,922 edges.
- `graphify tree --root .`: exactly `aria_nbv` and `docs` at the root.
- Thesis `main.typ` links to chapter indexes and inline appendix content.
- VIN-NBV `main.tex` links to its method and other included TeX sources.
- The descriptor plan at line 63 imports `RolloutZarrStoreReader` and
  `MultiStepCandidateScorer` and calls the real `q_h_view` method.
- No generated `symb_use`, `eqs_use`, citation-use, term-use, or code-reference
  wrapper nodes remain.
- Generated graph, reports, tree HTML, and wiki exports are ignored and no
  `graphify-out` path is tracked.

## Verification

- Graphify adapter and bridge tests: 38 passed.
- Repository retrieval contract: passed.
- `make graphify-ci`: passed.
- `make check-agent-memory`: passed before this debrief.
- `make wp7-integration-check`: passed; active scaffold LOC remains below the
  frozen baseline and tracked Graphify output is zero.
- `make scaffold-final`: passed.
- Independent verifier reproduced hierarchy, topology, direct-link, freshness,
  ignored-output, and installed-hook checks.

The implementation commits are `8c164876`, `0ac1e7c3`, and `14fe639f`.
Unrelated untracked transcript directories were left untouched.
