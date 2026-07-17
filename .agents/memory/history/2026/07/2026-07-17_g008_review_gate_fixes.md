---
id: 2026-07-17_g008_review_gate_fixes
date: 2026-07-17
title: "G008 Review Gate Fixes"
status: done
topics: [graphify, python-docstrings, quartodoc, ci]
confidence: high
canonical_updates_needed: []
files_touched:
  - .codex/skills/graphify/SKILL.md
  - .codex/skills/graphify/scripts/check_run_isolation.py
  - aria_nbv/aria_nbv/data_handling/__init__.py
  - scripts/quarto_generate_api_docs.sh
  - scripts/tests/test_quarto_generate_api_docs.sh
  - Makefile
---

## Task

Resolve the three G008 independent-review blockers without widening the
module-pruning follow-up: Graphify semantic-run isolation, the public
`data_handling` package contract, and Quartodoc stale-alias recovery semantics.

## Method and output

Graphify now captures one semantic run directory and substitutes that immutable
literal through B0-B3. The shared `.graphify_run_dir` file remains a visible
newest-run marker but is never reread by an active invocation. An executable
probe statically enforces the literal/manifest/no-glob contract and simulates a
pointer replacement before merge.

The `aria_nbv.data_handling` module docstring now documents raw ASE/EFM typed
views, immutable VIN read-side ownership, root-versus-leaf exports, and the
external ownership of Oracle generation and target selection. The targeted
docstring audit is clean; the repo-wide audit decreased from 32 to 31 findings,
with all remaining findings outside this change.

Quartodoc stale-page pruning now returns shell success exactly when it removed
a page. Its focused shell regression runs the real wrapper against a fake
builder that fails once with an alias error, verifies the stale page is pruned,
and proves the second build recovers without the no-page fallback message.
Both focused probes are root-CI prerequisites.

## Verification

- `make graphify-skill-self-test api-docs-self-test`
- Graphify skill validation
- targeted and repo-wide Python docstring audits
- `bash -n scripts/quarto_generate_api_docs.sh scripts/tests/test_quarto_generate_api_docs.sh`
- targeted Ruff format and lint
- `make api-docs`
- root agent-memory, package-smoke, and CI gates

## Canonical state impact

No canonical current-truth update is required. The owning skill, public package
docstring, executable regressions, and CI wiring now carry the durable contract.
