---
id: 2026-08-14_pr50_mandatory_graphify_workpackages
date: 2026-08-14
title: "PR50 mandatory Graphify workpackages"
status: done
topics: [graphify, scaffold, ci, worktrees]
confidence: high
canonical_updates_needed: []
---

## Task
Implement PR 50's mandatory Graphify workpackages: authoritative routing,
worktree-local seeding, upstream-first freshness, and hosted scaffold gating.

## Method
Kept the upstream Graphify skill byte-identical. Added a fail-closed seed helper
for linked worktrees, then replaced local manifest hashing with Graphify
0.9.31's `detect_incremental()` through the recorded interpreter. Hosted CI now
installs the pinned package and executes the matching scaffold contract.

## Findings
`scripts/setup_worktree_env.sh` seeds only local graph/projection artifacts and
links only semantic cache namespaces. `scripts/check_graphify_freshness.py`
now reports only `fresh`, `usable-stale`, or `unusable`; it isolates detector
cache/output in a temporary external `GRAPHIFY_OUT`. `.github/workflows/ci.yml`
and `scripts/ci_impact.py` route all Graphify, scaffold-audit, fixture, and
governance controls into the hosted scaffold lane.

The live checkout remains `unusable` as of 2026-08-14: its projection-owner
worktree is dirty and the upstream detector reports deleted manifest entries.
That is an artifact-repair condition, not a direct-source authority failure.

## Verification
Focused seed/setup, freshness, upstream-identity, CI-impact, Ruff, Python
compile, `git diff --check`, agent-memory, agent-DB, and scaffold-audit gates
were run during the workpackages. Hosted CI is configured to repeat them.

Focused local commits `f01a6f8f`, `ea41f079`, `3ac503e5`, and `15a5c134`
were created during the completed workpackages. No push or other external
publication was performed. Existing concurrent worktree changes were preserved.

## Canonical State Impact
None. The durable behavior is owned by source, tests, configuration, and the
accepted scaffold contract; this entry is historical evidence only.
