---
id: 2026-06-17_thesis_architecture_iteration21_acquisition_headroom
date: 2026-06-17
title: "Thesis Architecture Iteration 21 Acquisition Headroom"
status: done
topics: [thesis, architecture, evaluation, headroom, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/rl_planning.qmd
  - docs/contents/theory/rri_theory.qmd
  - docs/contents/thesis/roadmap.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 21 adds acquisition-curve and greedy-headroom guidance to the thesis
architecture autoresearch artifact. Endpoint target gain remains the primary
fixed-budget result. Curve AUC becomes a companion convergence-speed diagnostic,
and one-step greedy plus bounded oracle lookahead are empirical headroom
controls rather than formal submodularity guarantees.

## Evidence

- `.agents/memory/state/DECISIONS.md` already owns the comparison order:
  one-step scorer, one-step greedy, bounded oracle-RRI lookahead, then learned
  `Q_H` under equal acquisition and candidate budgets.
- `docs/contents/thesis/questions.qmd` and `docs/contents/thesis/roadmap.qmd`
  define the central question around finite-candidate `Q_H`, cumulative
  target-specific RRI, endpoint quality, and oracle-lookahead headroom.
- `docs/contents/theory/rl_planning.qmd` defines the bounded lookahead ladder
  and fixed-budget comparison.
- `docs/contents/theory/rri_theory.qmd` shows why undiscounted
  root-normalized target gain telescopes to endpoint target gain.
- `docs/typst/thesis/sections/05-experimental-design/index.typ` already treats endpoint gain
  as primary and `Q_H` as meaningful only when oracle lookahead has headroom.
- SCONE and MACARONS provide the useful reporting pattern of sequential NBV
  acquisition curves and AUC-style convergence summaries.
- Hestia provides a warning that future-return labels can create misleading
  current-action associations, making one-step greedy a serious control.
- VIN-NBV supports using reconstruction-quality objectives instead of coverage
  when the target metric is quality.
- Submodular and adaptive-submodular NBV records remain lineage for greedy
  controls, not proof that ARIA target-RRI has a greedy approximation guarantee.

## Canonical Updates Needed

- Add target-RRI acquisition curves and AUC companion metrics to the evaluation
  plan.
- Persist per-step target error, endpoint gain, cumulative root-normalized
  return, policy id, candidate profile, seed, horizon, selected candidate
  lineage, valid counts, and invalidity reasons in rollout/evaluation outputs.
- Add a submodularity caveat: greedy baselines are mandatory controls, but
  formal approximation guarantees require a separately proven monotone
  submodular target-RRI objective.
- Add proxy-mismatch diagnostics comparing coverage/Fisher/support curves
  against target-RRI residuals.
