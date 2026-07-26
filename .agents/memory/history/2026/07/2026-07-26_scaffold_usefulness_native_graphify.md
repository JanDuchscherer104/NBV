---
id: 2026-07-26_scaffold_usefulness_native_graphify
date: 2026-07-26
title: "Scaffold Usefulness And Native Graphify Repair"
status: done
topics: [scaffold, graphify, routing, evaluation]
confidence: high
canonical_updates_needed: []
files_touched:
  - scripts/graphify_adapter.py
  - scripts/graphify_bridge.py
  - .agents/skills/agent-behavior/SKILL.md
  - .agents/skills/aria-nbv-context/SKILL.md
  - .agents/references/human_owner_intent.md
  - .agents/references/scaffold_routing_fixtures.json
  - .agents/references/agent_memory_templates.md
  - AGENTS.md
artifacts:
  - graphify-out/graph.json
---

# Scaffold Usefulness And Native Graphify Repair

## Outcome

Graphify now finishes the native build step instead of treating raw extraction
as the final graph. Canonical path identities, resolved links, and native
communities therefore replace temporary IDs, dangling links, and a raw schema
that upstream commands could not consume. The repository still owns only the
corpus adapter and the Typst/TeX/Bib bridge that upstream does not provide.

Scaffold routing now reserves Graphify for unknown ownership, hierarchy,
architecture, impact, and cross-modal relationships. Exact files, named owners,
and operational skills route directly to their source. Restored guidance makes
completion checks, context handoffs, upstream-first integration, and TODO
disposition explicit without restoring domain primers to skills.

## Measured Evidence

| Probe | Before | After |
| --- | ---: | ---: |
| Dangling graph links | 1,187 | 0 |
| Native communities | 0 | 465 |
| Legacy path-ID warning | present | absent |
| Native benchmark | failed on missing `links` | 34.3x token reduction |
| Live task owner accuracy | 6/6 | 6/6 |
| Tasks routed through Graphify | 6/6 | 2/6 |

The paired source-only probe also reached 6/6 owner accuracy. This showed that
Graphify was useful for relational code/thesis and rollout-ownership questions,
but unnecessary for a named equation owner, measured-autoresearch policy,
human preferences, and dirty-worktree procedure. The routing contract was
narrowed on that evidence.

## Verification

- `make graphify-integration-self-test`: 39 passed.
- `scripts/tests/test_graphify_retrieval.py`: passed against the generated graph.
- `graphify benchmark`: 9,799 nodes, 18,251 resolved edges, 34.3x reduction.
- `make scaffold-audit`: 10 active skills, zero errors or warnings.
- `make check-agent-memory`: passed before this debrief.
- `scripts/scaffold/check_wp7_integration.py`: active scaffold LOC and prompt
  description budgets remain below baseline.

Implementation commits are `f862f3c0`, `e8abd9ac`, `fabbaae9`, and `49cc7b68`.
Unrelated thesis edits and transcript exports were left untouched.

## Canonical State Impact

Graph construction behavior is owned by the adapter, bridge, tests, and
`.agents/references/graphify_contract.md`. Routing is owned by `AGENTS.md`, the
two compact skills, and routing fixtures. Human integration preferences are
owned by `.agents/references/human_owner_intent.md`. This debrief is evidence,
not a second current-truth surface.

## TODO Disposition

No newly discovered source TODO requires an agents-DB record. A larger
behavioral benchmark can be run as a future measured-autoresearch mission when
there is a concrete scaffold candidate; no new evaluator framework was added.
