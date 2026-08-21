---
id: 2026-08-21_source_order_pointer_retirement
date: 2026-08-21
title: "Source-order compatibility pointer retirement"
status: done
topics: [agent-scaffold, source-order, simplification, agents-db]
confidence: high
canonical_updates_needed: []
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
---

## Task

Remove the shallow source-order compatibility pointer after its hierarchy,
conflict rule, and capture rule had moved to `aria-nbv-context`.

## Method

Locked the retired path in the ownership regression tests, migrated active
backlog and guidance consumers to exact scientific owners or focused
`aria-nbv-context` anchors, updated the accepted target-state supersession, and
deleted `.agents/references/source_order.md`. Historical plans, reports,
debriefs, and explicit negative validator fixtures retain the path as
provenance only.

## Findings

- The pointer contained no remaining policy and added an unnecessary routing
  hop.
- Active backlog records sometimes treated it as a scientific owner; those
  references now resolve to the thesis, theory, or implementation source that
  owns the claim.
- The retired destination guard remains necessary so future debriefs cannot
  revive the deleted path as a canonical update target.

## Verification

Agents-DB validation and the focused governance, ownership, CI-impact, and
retired-path tests passed after the migration. Broader scaffold and repository
verification is recorded in the associated pull-request update.

## Canonical-State Impact

`aria-nbv-context` is the sole agent-facing owner of source hierarchy, conflict
resolution, and capture routing. Scientific and implementation truth remains
with the exact Typst, bibliography, code, configuration, and test owners.
