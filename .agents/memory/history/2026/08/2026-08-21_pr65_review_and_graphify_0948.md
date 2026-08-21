---
id: 2026-08-21_pr65_review_and_graphify_0948
date: 2026-08-21
title: "PR 65 review remediation and Graphify 0.9.48"
status: done
topics: [agent-scaffold, review, graphify, context7, pull-request]
confidence: high
canonical_updates_needed: []
---

## Task

Verify the open PR #65 findings, apply valid repairs, migrate active Context7
routing away from Docker MCP, update Graphify to the latest release, and prove
the resulting Graphify workflow before publication.

## Method

Rebased the PR branch onto current `origin/main`, checked each review claim
against the nearest owner, and kept the root guidance and primary skills as
routers. Moved detailed semantic-memory, Graphify-boundary, and Python
verification rules behind focused references. Copied the repo-local Graphify
bundle from the installed upstream 0.9.48 skill and pinned its release commit
and tracked-file hashes in contract tests.

## Findings

- The derived context map needed an explicit non-owner label, a stronger route
  from `aria-nbv-context`, and path/label consistency tests.
- Semantic recall needed a fail-closed, read-only boundary that excludes code,
  tests, and configuration and requires current-source verification.
- Active Context7 calls now use the `@Context7` plugin/App tool names. Docker MCP
  Context7 remains only in migration, prohibition, or historical text.
- Graphify 0.9.48's installed hook performs code refresh and a bounded Markdown
  AST quick scan. Markdown changes still require an explicit semantic refresh
  before semantic-freshness claims; this ARIA-specific qualification stays in
  the local boundary while the vendored upstream skill remains byte-identical.
- Historical specifications retain their original Graphify pin; the accepted
  target-state supersession records the current 0.9.48 release.

## Verification

The focused governance suite passed with 68 tests and 75 subtests. Scaffold
audit reported zero errors, its 22 self-tests passed, agent-memory validation
passed, and both edited skills passed the skill validator. A clean temporary
repository proved Graphify extract, query, path, explain, hook installation,
code-triggered refresh, and the documented Markdown behavior. Full CI passed
the 293-test main package suite; its separate smoke slice passed 114 tests and
had one environment-only CUDA/PyTorch3D build mismatch, whose exact test passed
with CUDA hidden as required for the installed CPU-only extension.

## Canonical-State Impact

Guidance owners, routing fixtures, tool-reference validation, Graphify release
gates, CI pinning, migration receipts, and focused tests changed. No scientific
claim or Python runtime behavior changed.
