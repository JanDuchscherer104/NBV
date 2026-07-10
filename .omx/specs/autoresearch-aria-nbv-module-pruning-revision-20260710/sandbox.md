# Sandbox And Evidence Contract

## Scope

Read-only architecture research over:

- `aria_nbv/aria_nbv/rri_metrics/**`
- `aria_nbv/aria_nbv/rollouts/**`
- `aria_nbv/aria_nbv/pipelines/**`
- relevant `aria_nbv/aria_nbv/data_handling/**`
- direct consumers in Lightning, VIN, app panels, scripts, and tests
- related `.omx` plans/specs/state from 2026-07-08 and 2026-07-09

No Python implementation refactor is authorized in this research iteration.

## Evidence Methods

- Existing Graphify graph queried before raw code traversal.
- Deterministic `rg`, `tree`, `wc`, and numbered source reads.
- Independent Explore and code-review subagents.
- Current package guidance and public-contract tests.

## Working-Tree Safety

The worktree contains unrelated user and agent changes. Preserve them. Durable
writes are limited to this new research artifact, a minimal status banner on the
latest draft plan after validation, and the required debrief.

## Current Baseline

Active Python LOC at the inspected revision:

| Module | LOC |
|---|---:|
| `rri_metrics` | 4,150 |
| `rollouts` | 9,660 |
| `pipelines` | 178 |
| `data_handling` | 9,696 |
| **Total** | **23,684** |

The implementation RALPLAN must re-record this baseline at its own starting
commit. This snapshot is evidence for plan review, not a future merge metric.
