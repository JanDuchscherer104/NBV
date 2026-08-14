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

An independent final review later found fail-open gaps around destination-parent
symlinks, projection and root-marker validation, and upstream detector coverage
fields. G006 remediated those gaps with fail-closed parent-chain, marker, scope,
and detector-result validation. This records remediation evidence, not final
review approval.

G007 then found that setup's shell-level `mkdir -p graphify-out/cache` could
still follow a child `graphify-out` or `graphify-out/cache` symlink before the
seed guard ran. Setup now reuses the Python parent-chain guard through a narrow
cache-preparation mode before directory creation and again immediately before
linking only the `semantic` and `semantic-deep` cache leaves. This remediation
also does not constitute final review approval.

The user-directed G008 follow-up added Graphify 0.9.31's generated always-on
`## graphify` section to the agents-DB guide, followed by the mandatory ARIA
freshness and exact-source reconciliation. It also removed stale active wording
that called the required projection optional. G008 created no backlog record and
does not assert final review approval.

## Verification
Focused seed/setup, freshness, upstream-identity, CI-impact, Ruff, Python
compile, `git diff --check`, agent-memory, agent-DB, and scaffold-audit gates
were run during the workpackages. Hosted CI is configured to repeat them.
G006 also added and passed eight focused seed regressions and seven focused
freshness regressions.
G007 expanded the seed suite to eleven regressions and added setup coverage for
existing and dangling external targets in bootstrap, idempotent, and `--check`
paths; the live setup `--check` also passed.
G008 passed agents-DB validation/listing, agent-memory validation, twelve G002
governance tests, forty-two projection tests, scaffold audit/self-test, upstream
skill identity, Ruff, Python compilation, and whitespace validation.

The final review follow-up restored compact, routed review, Python, testing,
upstream-reuse, EFM-key, and rollout DTO/target boundaries. It removed the
unconsumed Quarto agent-doc generator and added a focused governance regression
that prevents those routes from becoming circular or disappearing again.

A later owner clarification made architect and critic review outputs
session-local rather than versioned plan artifacts. Eleven unconsumed role-review
files were removed; root guidance, memory capture policy, ignore rules, and G002
now preserve only accepted decisions and actionable findings in canonical owners.

Focused local commits `f01a6f8f`, `ea41f079`, `3ac503e5`, `15a5c134`,
`e98e3027`, `2c902989`, and `a30d64c4` were created during the completed
workpackages. No push or other external publication was performed. Existing
concurrent worktree changes were preserved.

## Canonical State Impact
None. The durable behavior is owned by source, tests, configuration, and the
accepted scaffold contract; this entry is historical evidence only.
