---
id: 2026-08-22_readme_routing_refresh
date: 2026-08-22
title: "README routing refresh"
status: done
topics: [documentation, routing, onboarding, thesis]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - README.md
  - SETUP.md
  - aria_nbv/README.md
  - docs/index.qmd
  - scripts/tests/test_ownership_consolidation_contract.py
codex_thread: codex://threads/019fff4c-cc77-7351-bb81-9759852617c6
repo_object_format: sha1
repo_head: 3dacdabcb60b797ef5478f280a3784019b62ddbd
repo_branch: "codex/readme-routing-refresh"
worktree_kind: linked
---

## Task
Refresh the project landing page and its public companion surfaces so readers
reach current research, setup, data, rollout, training, and scientific owners.

## Method
Audited `origin/main` against the active Typst research questions, package
metadata, setup guide, module READMEs, and executable entrypoints. Graphify
classified the inherited snapshot as `unusable`, so no graph query was used and
all consequential claims were verified from direct owners. Replaced duplicated
status prose with progressive routing, then completed an independent review and
resolved every finding before commit `3dacdabcb60b797ef5478f280a3784019b62ddbd`.

## Findings
`README.md` now states the durable actor/oracle, finite-candidate, two-store, and
matched-evaluation ideas; distinguishes available infrastructure, active gates,
and deferred work; and routes each common goal to its smallest owner.
`aria_nbv/README.md` no longer publishes the obsolete seminar title and URL.
`docs/index.qmd` now matches the active thesis gates. `SETUP.md` no longer names
the retired `nbv-rollout-trace-smoke` entrypoint. The ownership regression now
checks public-document links, registered CLI names, and tracked config examples.

## Verification
- `make ... docs-render-core package-smoke`: passed; 293 `Q_H` tests and 115
  package smoke tests passed, with existing dependency warnings only.
- `quarto render docs/index.qmd --no-execute`: passed.
- `make ... ownership-consolidation-contract qmd-frontmatter-check
  check-agent-memory`: passed before debrief capture; focused contract rerun
  passed 21 tests after the final review fix.
- `uv build`: wheel and source distribution built successfully in a disposable
  temporary directory.
- Ruff and `git diff --check`: passed. Independent final review reported zero
  actionable findings; LSP diagnostics were unavailable.

## Canonical Owner Impact
Updated the public root router (`README.md`), portable setup owner (`SETUP.md`),
packaged landing page (`aria_nbv/README.md`), public Quarto landing page
(`docs/index.qmd`), and their direct-source regression contract. The active
Typst thesis and executable package owners were not changed.
