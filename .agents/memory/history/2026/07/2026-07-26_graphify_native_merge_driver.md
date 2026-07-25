---
id: 2026-07-26_graphify_native_merge_driver
date: 2026-07-26
title: "Native Graphify Merge Driver Adoption"
status: done
topics: [graphify, scaffold, simplification]
confidence: high
canonical_updates_needed: []
---

## Task and Outcome

Delete the repository-local Graphify merge-driver wrapper while preserving
`.gitattributes` assignment. `make graphify-setup` now resolves the existing
pinned Graphify command and configures upstream `merge-driver` directly; the
integration and WP7 checks reject stale wrapper ownership.

## Verification

Python compilation, focused Graphify integration checks, the WP7 budget
self-test, `make graphify-setup`, and a native merge-driver smoke test passed.
`git diff --check` and the `.gitattributes` no-diff check passed. Ruff formatted
the two touched Python files with the shared ARIA environment.

## Canonical State Impact

No further canonical updates are needed. The Makefile and focused integration
checks own the native setup contract; no graph artifacts or corpus surfaces
changed.
