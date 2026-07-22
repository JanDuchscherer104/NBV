---
id: 2026-07-22_wp6_litkg_generated_context_retirement
date: 2026-07-22
title: "WP6 LitKG And Generated-Context Retirement"
status: done
topics: [scaffold, litkg, generated-context, exact-source]
confidence: high
canonical_updates_needed:
  - .agents/references/direct_source_claim_checklist.md
  - .agents/references/source_order.md
  - .agents/todos.toml
---

## Task

Completed approved scaffold-refresh WP6 after WP5 by closing the capability
disposition ledger, removing active LitKG and broad generated-context routes,
and retaining bounded exact-source inspection.

## Method

Removed the LitKG submodule, configuration, skills, commands, scripts, hooks,
and runtime/MCP wiring. Removed aggregate context generation and inventories
while preserving literature manifests, TeX mirrors, bibliography, historical
debriefs, contract/QMD/Typst/tree inspection, and one path-scoped UML command.

## Output

The active scaffold contains exactly nine skills. Advisor-facing claims now use
the direct-source checklist. The package-wide docstring checker and package
README ownership audit remain explicitly deferred in the agents DB.

## Verification

Passed scaffold audit and self-test, retired-route scanning, literature-owner
checks, direct-source fixtures, hermetic scoped-UML tests, agents-DB validation,
agent-memory validation, shell syntax checks, Python compilation, and diff
whitespace checks.

## Canonical State Impact

Exact repository sources, bibliography keys, durable paper identifiers, and
authoritative URLs replace active LitKG evidence routes. Historical LitKG
debrief bodies and baseline ledgers remain evidence only, not active routing.
