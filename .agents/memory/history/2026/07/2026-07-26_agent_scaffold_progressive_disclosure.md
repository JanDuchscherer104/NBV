---
id: 2026-07-26_agent_scaffold_progressive_disclosure
date: 2026-07-26
title: "Agent Scaffold Progressive Disclosure"
status: done
topics: [scaffold, skills, progressive-disclosure, autoresearch, g006]
confidence: high
canonical_updates_needed: []
---

## Task

Complete G006 by compacting the agent scaffold around progressive disclosure,
restoring the measured-autoresearch iteration contract, and disposing of stale
generated navigation and inline TODO surfaces without changing runtime behavior.

## Outcomes and boundaries

G006 landed as these commits:

- `48dc7070`: deleted generated-navigation helpers and static Rerun indexes.
- `e0300562`: restored mixed research/inspiration and
  implementation/measurement measured-autoresearch iterations.
- `40a36caa`: compacted docs, context, and plan skills.
- `64d8b196`: compacted operator skills.
- `96c4fecf`: restored compact `agent-behavior` and established the 10-skill,
  prompt-budget, and scaffold-audit contract.
- `0ce5946a`: disposed of inline data TODOs and deleted the stale README tree.
- `25e2250a`: recorded the required graph-only child.

Skills own workflow and routing only. The active thesis, package code, tests,
and their nearest guidance remain the exact scientific, implementation, and
verification owners. Localization is Graphify-first with exact-source
verification. Static Context7, literature, and tool inventories are optional,
not required. Native Graphify is navigation infrastructure, not source
authority for skills or debriefs.

## Measured-autoresearch evidence

Mission `.omx/goals/autoresearch/scaffold-skill-compaction-20260726` compared
baseline `b1d599fc` with candidate `96c4fecf` under contract digest prefix
`aa2b...`; the primary result improved and was kept. Tracked skill LOC fell
from 4,271 to 2,143, ARIA description bytes from 500 to 380, and active
scaffold LOC from 23,086 to 20,757. Skill count increased from 9 to 10 while
validation failures remained 0 to 0. The three residual stale-name hits are
intentional negative sentinels in `check_wp7_integration.py`, not live routes.
The 1.4 GB temporary tar and worktrees were removed; the final ignored mission
occupies 436 KB.

## TODO disposition

The request to restore research/inspiration versus implementation/measurement
iteration types was resolved by `e0300562`. Five generated navigation helpers
and two static Rerun maps were deleted. Eight `inventory.py` inline TODO
comments were consolidated under `todo-097` without behavior change, and the
stale README HTML TODO block was deleted. Active Typst TODO-like matches are
typed draft markers with exact `.agents/todos.toml#todo-*` owners. TOML
`status = "todo"` entries are the canonical backlog, not free-floating
comments. No unresolved G006 inline TODO remains; G007 owns integrated final
review, visual, and invariant checks.

## Adjusted attempts

The upstream Graphify query for draft markers was broad, so exact-source
fallback confirmed ownership. The initial source commit hook did not refresh
the graph in this worktree; adapter sync and the required graph-only child were
therefore run explicitly. The first TODO executor stalled and was replaced.
Broad static metadata registries were removed rather than repaired.

## Verification

Validation covered 10 `quick_validate` runs; scaffold audit at 0 errors and 0
warnings; scaffold self-test; Matt self-test; all 9 measured-helper tests; WP7
at `380 + 1008 = 1388 <= 1511`; agent-memory checks; LRZ Bash syntax;
inventory Ruff, compile, and 3 tests; agents DB; and Graphify history and
freshness checks.

## Canonical state impact

None. The commits above updated the exact owners; this debrief records their
completed G006 evidence and leaves `canonical_updates_needed: []`.
