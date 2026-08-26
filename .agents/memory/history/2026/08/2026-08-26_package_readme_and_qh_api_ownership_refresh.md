---
id: 2026-08-26_package_readme_and_qh_api_ownership_refresh
date: 2026-08-26
title: "Package README and QH API ownership refresh"
status: done
topics: [documentation, qh-scorer, api-reference, ownership]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - README.md
  - aria_nbv/README.md
  - aria_nbv/aria_nbv/vin/README.md
  - aria_nbv/aria_nbv/lightning/README.md
  - docs/reference/_sidebar.yml
codex_thread: codex://threads/01a033b8-ed20-76a0-9627-2679b556cbff
repo_object_format: sha1
repo_head: 4ce9b9957aadcc5d2fe1bd49644ce2e6e89d91df
repo_branch: "codex/readme-agents-refresh"
worktree_kind: linked
---

## Task
Replace stale refactor-era package notes with user-facing guides aligned to the
merged multi-step QH scorer, while keeping implementation semantics in code,
public docstrings, tests, configuration, and the thesis.

## Method
Read the nearest package and documentation guidance, traced the current QH
workflow through exact source and tests, rewrote package README surfaces,
clarified AGENTS ownership boundaries, expanded public contract docstrings, and
regenerated the canonical API navigation and dependency metadata.

## Findings
- `README.md` and `aria_nbv/README.md` now route users by workflow and state the
  documentation ownership hierarchy explicitly.
- Package READMEs under `aria_nbv/aria_nbv/` now describe supported entry
  points, data flow, invariants, and focused verification instead of preserving
  migration inventories.
- `aria_nbv/aria_nbv/vin/README.md` and
  `aria_nbv/aria_nbv/lightning/README.md` document the conditional-Q boundary,
  scalar requested horizon, hard-mask ownership, regression/CORAL decoding,
  scene profiles, and bundle lifecycle with linted Mermaid diagrams.
- Public package and scorer/training docstrings now carry the symbol-level
  contracts exposed through generated API reference pages.

## Commits
- [4ce9b9957aadcc5d2fe1bd49644ce2e6e89d91df](https://github.com/JanDuchscherer104/ARIA-NBV/commit/4ce9b9957aadcc5d2fe1bd49644ce2e6e89d91df)

## Verification
- Ruff lint and format check passed for all `aria_nbv` sources and tests.
- Focused data, rollout, oracle, VIN, Lightning, Q2, and one-epoch training tests
  passed: 353 tests.
- Ownership/governance and API-doc self-tests passed: 41 tests plus
  `make api-docs-self-test`.
- README links, Python examples, Mermaid sources, public docstrings, documented
  CLI help, and targeted Quarto API pages passed their focused checks.
- A targeted mypy invocation still reports pre-existing Lightning typing debt;
  this documentation-only change did not modify those executable signatures.

## Canonical Owner Impact
No behavior, configuration, tests, or Typst claims changed. Public docstrings,
package README guides, documentation/agent routing, and generated API metadata
were updated to describe the already-merged implementation.
