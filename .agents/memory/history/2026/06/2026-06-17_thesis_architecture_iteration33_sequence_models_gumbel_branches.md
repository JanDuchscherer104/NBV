---
id: 2026-06-17_thesis_architecture_iteration33_sequence_models_gumbel_branches
date: 2026-06-17
title: "Thesis Architecture Iteration 33 Sequence Models And Gumbel Branches"
status: done
topics: [thesis, architecture, q-h, rollout-diversity, sequence-modeling, gumbel-top-k]
confidence: high
canonical_updates_needed:
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/rl_planning.qmd
  - aria_nbv/aria_nbv/rollouts/replay/engine.py
  - aria_nbv/tests/rollouts/test_counterfactuals.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 33 separated sequence-model RL bridge ideas from rollout-diversity
knobs. Decision Transformer and Trajectory Transformer should remain later
sequence-policy or sequence-planner baselines because they would replace several
typed ARIA-NBV contracts at once. Gumbel-Top-k is a better near-term transfer:
it can improve no-replacement branch diversity while preserving the finite
candidate `Q_H` replay and evaluation contract.

## Evidence

- Canonical memory locks random-valid, oracle-greedy/lookahead, and
  oracle-scored temperature-softmax traces before first `Q_H`; Gumbel-Top-k is
  preferred later diversity evidence, not a blocker.
- `docs/contents/thesis/questions.qmd` and `roadmap.qmd` place Decision
  Transformer, CQL/BCQ/IQL, and Gumbel-Top-k behind deterministic rollout trust.
- `aria_nbv/aria_nbv/rollouts/replay/engine.py` currently implements
  random/random-valid, oracle-greedy, and temperature-softmax selection, plus
  branch factor, beam width, stochastic branch-factor schedules, robust logits,
  and diversity guards.
- `aria_nbv/tests/rollouts/test_counterfactuals.py` verifies
  temperature-softmax invalid masking, reproducibility, distinct candidate
  sampling, affine score-scale invariance, beam-width caps, and stochastic
  branch-factor reproducibility.
- The local Decision Transformer and Trajectory Transformer TeX sources motivate
  return-conditioned policy generation and beam-search trajectory modeling, but
  also introduce behavior imitation, discretization, model likelihood, and
  learned-transition risks.
- The local Gumbel-Top-k source provides the direct no-replacement branch
  sampling transfer for low-entropy finite candidate distributions.

## Canonical Updates Needed

- Keep Decision Transformer and Trajectory Transformer as separate future
  `sequence_policy` / `sequence_planner` baselines, not replacements for the
  primary finite-candidate `Q_H` result.
- If Gumbel-Top-k branch selection is implemented, persist score source,
  temperature, RNG seed, perturbation or reproducible seed material, selected
  order, no-replacement rank, threshold/inclusion metadata when used, diversity
  metrics, and branch lineage.
- Update rollout-support thesis text to say Gumbel-Top-k is a diversity upgrade
  after deterministic and temperature-softmax replay are trusted.
- Keep `Q_H` claims tied to oracle-rescored selected actions under equal target,
  candidate, mask, and budget contracts.
