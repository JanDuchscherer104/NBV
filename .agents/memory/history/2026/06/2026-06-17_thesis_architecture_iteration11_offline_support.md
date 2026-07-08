---
id: 2026-06-17_thesis_architecture_iteration11_offline_support
date: 2026-06-17
title: "Thesis Architecture Iteration 11 Offline Support"
status: done
topics: [thesis, literature, q-h, offline-rl, rollouts]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/rl_planning.qmd
  - docs/contents/literature/rl_planning.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing offline replay support,
stochastic branch diversity, and fitted value-backup choices for the planned
finite-candidate `Q_H`.

## Findings

The `Q_H` architecture is only interpretable under the behavior-policy mixture
that generated selected-action transitions. Random-valid, one-step oracle
greedy, bounded oracle lookahead, oracle-scored temperature-softmax, and later
Gumbel-Top-k traces should be reported as behavior-policy families before
learned `Q_H` metrics.

DQN motivates replay and held-out predicted-Q diagnostics. Double DQN motivates
masked selector/evaluator backups and overestimation plots. CQL and IQL
motivate support-aware diagnostics after fitted Double-Q is stable, but they
are not shortcuts around the mandatory finite-candidate `Q_H` result.

Stochastic traces require replayable provenance: seeds, policy hashes, logits or
scores, normalization statistics, probabilities/log-probs, entropy, sampled
outcomes, Gumbel keys when used, parent/selected chain ids, selected action, and
successor candidate-table references.

## Canonical State Impact

The autoresearch report now adds a behavior-policy mixture table, replay-support
diagnostics, backup ladder, stochastic provenance contract, and failure
interpretation order for `Q_H`.

Follow-up thesis edits should include replay-support diagnostics and
offline-backup evidence in the evaluation plan. Follow-up implementation audits
should compare rollout writer/Zarr fields against the selected-transition and
stochastic-provenance requirements.

## Verification

- Local scans covered `docs/contents/literature/rl_planning.qmd`,
  `docs/contents/theory/rl_planning.qmd`,
  `.agents/work/rollout-scale-readiness`, and local DQN, Double DQN, CQL, IQL,
  BCQ, Decision Transformer, Trajectory Transformer, and Gumbel-Top-k TeX
  sources.
- `make kg-route` returned decisions, roadmap/questions,
  counterfactual-rollout skill guidance, active stochastic-branch TODOs, rollout
  writer/Zarr implementation, and tests as the owner stack for offline support.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
