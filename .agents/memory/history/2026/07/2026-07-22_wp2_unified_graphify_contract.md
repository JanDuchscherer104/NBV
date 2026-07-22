---
id: 2026-07-22_wp2_unified_graphify_contract
date: 2026-07-22
title: "WP2 Unified Graphify Contract"
status: done
topics: [graphify, scaffold, provenance]
confidence: high
canonical_updates_needed: []
---

Implemented approved WP2 as one source-derived graph with code, scaffold,
thesis, and literature partitions. The canonical graph records role tags,
partition revisions, bridge revisions, exact source locators/digests, and
separate categorical origin and numeric confidence. Structural refresh retains
source-valid inferred edges; semantic partitions require explicit sync.

Only `graph.json`, `manifest.json`, and `GRAPH_REPORT.md` are tracked. Focused
fixtures cover corpus classification, provenance rejection, partition and
bridge staleness, exact-source fallback, asynchronous hook dispatch, and S-to-G
history validation. Canonical no-diff regeneration uses pinned
`graphifyy==0.9.22` and remains below the 35 MB output budget.
