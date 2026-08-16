---
kind: spec
status: accepted
---

# Ownership and branch-consolidation successor spec

Status: compact accepted-scope pointer for S1/S2 execution; it is not a
scientific, implementation, or canonical-memory owner.

## Ownership contract

- Active Typst include graph (`docs/typst/thesis/main.typ`) owns thesis theory,
  RQ1-RQ4, definitions, hypotheses, interpretation, and scientific claims.
- Python/config/types/docstrings plus focused tests own executable behavior,
  schemas, lifecycle, frames, failure modes, and implementation details.
- Quarto owns only role-disjoint public setup/commands, generated API,
  literature dossiers, external background, and navigation.
- `.agents/memory/state/` is retired after paragraph/bullet disposition and
  destination proof. Dated history and resolved receipts remain provenance.
- `.omx/` owns coordination receipts and verification only; it must not become a
  replacement theory, contract, or canonical-memory layer.

## Migration reservations

| lane | reserved destination | owner | proof before deletion |
|---|---|---|---|
| RQ | `docs/typst/thesis/sections/01-research-questions.typ` and reserved introduction include | leader/RQ lane | exactly four active RQs; no QMD duplicate |
| roadmap | `docs/typst/thesis/development/roadmap.typ` | roadmap lane | development-only render; pointer-only entries |
| M1 | `docs/typst/thesis/development/m1-contract-report.typ` | M1 lane | status/evidence links resolve; contracts remain code/test-owned |
| state migration | Typst/Python/config/tests/guidance owners | migration lane | every unique row destination_verified=true |
| Quarto/navigation | `docs/_quarto.yml`, inbound links, expected-page manifest | leader | wildcard preserved; no removed routes |
| generated/context | source index, agent-doc generators, Graphify artifacts | scaffold lane | no live state-file consumer; freshness gate passes |
| branch/PR | `.omx` receipt only | leader | exact head/base/tree/diff/check/thread evidence |

## Lane rules

1. A planned path is not a verified destination. Set `destination_verified` to
   true only after the exact owner path and section/symbol exist and its focused
   check passes.
2. Agents-DB records may contain only problem/why-now, canonical owner pointer,
   acceptance, and gate. They never satisfy destination coverage.
3. Do not copy theory, equations, schemas, or contracts into ledgers/specs;
   use subjects, pointers, hashes, and dispositions.
4. Every source block and branch/PR receives a disposition. `unresolved` is
   permitted only for content awaiting materialization and must name its exact
   destination and gate.
5. Preserve unrelated dirty work and do not stage, commit, push, comment,
   merge, close, retarget, or delete branches/worktrees in this lane.

## Stop conditions

S1 stops when all seven retired sources and all theory pages have row-level
coverage, all live consumers have a removal/replacement pointer, and the
baseline receipt gap is either closed or explicitly blocks the next stage.
S4 deletion is blocked while any unique row is unresolved or has
`destination_verified: false`, and while hosted PR50 checks/review state remain
unverified. JSON/Markdown row counts and `git diff --check` are mandatory.
