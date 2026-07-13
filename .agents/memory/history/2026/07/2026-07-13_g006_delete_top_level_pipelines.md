---
id: 2026-07-13_g006_delete_top_level_pipelines
date: 2026-07-13
title: "G006 Delete Top-Level Pipelines"
status: done
topics: [pipelines, oracle, public-api, simplification]
confidence: high
canonical_updates_needed: []
---

# G006 Delete Top-Level Pipelines

## Scope

Deleted the empty `aria_nbv.pipelines` transition package after scene labels,
rollout generation, shard execution, and CLI composition had moved to
`aria_nbv.oracle.pipelines`.

## Changes

- Deleted the empty package marker and transition README.
- Strengthened the public API contract to require the namespace itself to be
  absent, not only the former scene-label leaf.
- Removed the obsolete package from generated API navigation.

Production Python LOC decreased from 67,947 to 67,944 (-3), and the package
count decreased by one.

## Verification

- Repository-wide production, test, config, and active-doc scans found no live
  callers before deletion.
- Import, app-state, Oracle API, CLI, compileall, Ruff, Quartodoc, and Graphify
  checks passed after deletion.
- Historical transcript and archive references were retained as provenance.

## Canonical Updates Needed

- None. Active callers and generated API navigation now point only to the
  owning Oracle pipeline leaves.
