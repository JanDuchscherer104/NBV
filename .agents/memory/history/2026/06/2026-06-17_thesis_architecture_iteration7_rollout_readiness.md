---
id: 2026-06-17_thesis_architecture_iteration7_rollout_readiness
date: 2026-06-17
title: "Thesis Architecture Iteration 7 Rollout Readiness"
status: done
topics: [thesis, literature, q-h, rollouts, zarr]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/rl_planning.qmd
  - docs/contents/theory/candidate_view_dependence.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by linking the planned model ladder to
the rollout-store fields, support coverage, and preflight evidence needed to
make each architecture comparison meaningful.

## Findings

The architecture ladder should be a sequence of falsifiable experiments, not a
model menu. Each stage needs corresponding `rollouts.zarr` fields: candidate
ids, row ids, `position_id`, strategy/mixture/probability provenance, masks,
invalidity bitsets, support diagnostics, selected-transition lineage, successor
candidate tables, rewards, returns, oracle-rescored validation returns, and
scene-level split/seed lineage.

The store preflight should run before model metrics are interpreted. It should
fail broad generation on stale schema, missing selected-transition lineage,
missing provenance fields, inconsistent invalidity bits, low-valid roots,
candidate-family collapse, flat rewards, missing stochastic replay provenance,
split leakage, or excessive chunk/file counts.

The recurring `position_id` audit warning is scientifically important. If the
candidate generator emits a provenance axis that is not persisted, later claims
about position-family support, validity, headroom, or learned policy behavior
are not auditable.

## Canonical State Impact

The autoresearch report now includes an ablation matrix that maps A0-A7 stages
to literature support, required rollout fields, pass/fail evidence, and blocker
interpretations. Follow-up thesis edits should place the model ladder beside
the rollout-data contract and report preflight/support coverage before model
metric tables.

## Verification

- Local scans covered `rollouts.zarr`, Zarr chunking, production preflight,
  invalidity, candidate provenance, `position_id`, support coverage,
  selected-transition lineage, and model evaluation metrics in
  `docs/contents/theory`, `docs/contents/thesis`, and `.agents/work`.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
