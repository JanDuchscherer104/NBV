---
id: 2026-06-17_thesis_architecture_iteration4_value_learning
date: 2026-06-17
title: "Thesis Architecture Iteration 4 Value Learning"
status: done
topics: [thesis, literature, offline-rl, q-h, rollouts]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/thesis/roadmap.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing finite-candidate `Q_H`
through local value-learning and offline-RL literature.

## Findings

`Q_H` should be framed as an offline finite-action value estimator over
logged/generated candidate sets. DQN supports replay rows and all-action value
heads, but ARIA-NBV needs row-equivariant set outputs rather than fixed action
indices. Double DQN motivates decoupled argmax/evaluation backups to reduce
overestimation.

CQL and IQL reinforce that support coverage and in-sample candidate actions
matter before policy improvement. Decision Transformer and Trajectory
Transformer remain useful future sequence/planning baselines but should not
replace direct finite-candidate value learning. Gumbel-Top-k is best placed in
stochastic branch generation after deterministic traces are trustworthy.

## Canonical State Impact

The autoresearch report now includes a `Q_H` training-row contract and value
evaluation controls: replay lineage, candidate validity, support counts,
oracle-rescored validation returns, overestimation diagnostics, matched-budget
policy comparison, and stochastic branch diversity reporting.

## Verification

- Local TeX scans covered DQN, Double DQN, CQL, IQL, Decision Transformer,
  Trajectory Transformer, and Gumbel-Top-k.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
