---
id: 2026-07-19_graphify_freshness_and_docstring_recovery
date: 2026-07-19
title: "Graphify Freshness And Docstring Recovery"
status: done
topics: [graphify, python-docstrings, progressive-disclosure, rollouts, oracle]
confidence: high
canonical_updates_needed: []
files_touched:
  - AGENTS.md
  - .graphifyignore
  - scripts/git_hooks/post-commit
  - scripts/graphify_refresh.py
  - scripts/check_graphify_freshness.py
  - scripts/check_graphify_integration.py
  - aria_nbv/aria_nbv/rollouts/replay/state.py
  - aria_nbv/aria_nbv/oracle/labels.py
---

## Task

Review the post-refactor Graphify integration and recover still-valid spatial
and temporal docstring contracts from the pre-refactor enrichment.

## Method And Findings

The tracked post-commit hook terminated in the litkg branch before Graphify
could run and embedded a Linux-user-specific interpreter plus private Graphify
internals. The hook now composes both refreshes and delegates Graphify lifecycle
work to one repository module using the supported CLI. Local navigation is
fail-closed on commit, corpus-policy digest, and pending semantic extraction.

Graphify 0.9.20 detection found 310 intended sources after excluding generated
Quarto support trees and local graph memory. Package code remains the structural
backbone; Quarto, Typst, literature summaries, SVG thesis diagrams, and curated
agent references provide semantic bridges without indexing runtime state or
bulk generated media.

The refactor moved rollout and oracle DTOs correctly but left detailed axis and
frame contracts behind in deleted modules. The current owners now document the
full shell ``N``, compact-valid ``V``, horizon ``H``, path ``T``, and beam ``L``
axes, world-frame metres, padded point lengths, and privileged-evidence seam.
Deleted compatibility modules remain deleted.

## Verification

- `make graphify-integration-self-test graphify-skill-self-test PYTHON_INTERPRETER=/opt/homebrew/bin/python3`
- Ruff format and lint on changed Python files
- Python `compileall` and POSIX shell syntax checks
- Normalized AST equality for the two docstring-only package edits
- Targeted package pytest was attempted but blocked by the current native
  PyTorch3D extension linking against an incompatible Torch C++ symbol on macOS

## Canonical State Impact

No thesis or project-state claim changed. Root guidance and the verification
matrix now own the durable Graphify freshness contract.
