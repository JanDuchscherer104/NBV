---
id: 2026-08-02_graphify_trusted_default_and_freshness_gates
date: 2026-08-02
title: "Graphify Trusted Default And Freshness Gates"
status: done
topics: [graphify, scaffold, hooks, freshness]
confidence: high
canonical_updates_needed: []
files_touched:
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/agent-behavior/references/external-actions.md
  - .agents/skills/aria-nbv-context/SKILL.md
  - .agents/skills/aria-nbv-context/references/graphify-aria-boundary.md
  - .pre-commit-config.yaml
  - .gitattributes
  - Makefile
  - scripts/check_graphify_freshness.py
  - scripts/tests/test_graphify_freshness.py
  - scripts/tests/test_ci_impact.py
  - scripts/tests/test_graphify_upstream_skill.py
---

## Task

Make an existing Graphify graph the default retrieval index instead of globally
disabling it whenever its build commit differs from Git HEAD. Keep strict state
validation around scaffold closeout and Git hooks.

## Method And Findings

The live graph was valid but rejected by a commit-equality gate. Graphify's
post-checkout rebuild can deliberately leave outputs untouched when code
topology does not change, so `built_at_commit == HEAD` was not a sound content
freshness predicate. The post-commit hook was also missing, and the broad graph
query was bypassed by ARIA guidance whenever the strict check returned nonzero.

The checker now treats ancestor-only revision drift as valid and compares every
indexed source against Graphify's content-addressed manifest. It reports
`usable`, `graph_revision`, and `stale_sources`; stale but structurally valid
graphs remain queryable by default, while missing or invalid graphs do not.
It also detects currently admitted sources missing from an old manifest and
includes changed projection owners in `stale_sources`. Consequential results
from stale source locations are verified directly.

Local make targets split ordinary usability from strict closeout freshness.
Pre-commit validates a snapshot when present without requiring this optional
artifact; pre-push and `scaffold-check` run the strict state check. Upstream
post-commit and post-checkout hooks plus the Graphify merge
driver were installed without modifying the byte-identical upstream skill.
`agent-behavior` now also treats an explicitly authorized push and pull request
as part of task completion through its conditional external-action reference,
while retaining the per-action authorization and path-scoped staging boundary.
Graphify build, refresh, marker, and worktree mechanics likewise live behind a
build-or-refresh context pointer instead of expanding the discovery router.

## Verification

- Graphify freshness tests: 17 passed.
- CI-impact tests: 12 passed.
- Upstream Graphify skill tests: 2 passed.
- Focused Ruff format and lint passed.
- `make graphify-usable-check` passed on the live usable snapshot.
- `make scaffold-check` ran all deterministic scaffold checks and then failed at
  the intended strict Graphify gate because 30 indexed sources genuinely differ
  from the current manifest.
- `make check-agent-memory` and `git diff --check` passed.

## Canonical-State Impact

No separate state file is needed. The executable checker, Make targets,
pre-commit configuration, and ARIA context-routing skill are the current owners
of the new trusted-default and strict-closeout behavior.
