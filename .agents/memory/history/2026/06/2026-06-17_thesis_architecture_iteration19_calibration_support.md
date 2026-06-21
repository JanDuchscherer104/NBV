---
id: 2026-06-17_thesis_architecture_iteration19_calibration_support
date: 2026-06-17
title: "Thesis Architecture Iteration 19 Calibration Support"
status: done
topics: [thesis, architecture, calibration, q-h, offline-rl]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/thesis/roadmap.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 19 separates target-RRI calibration, uncertainty/support diagnostics,
invalidity masks, finite-horizon value estimation, Double-Q backup checks, and
CQL/IQL-style support ablations. The architecture should not collapse these
signals into one reward or one scalar uncertainty bonus.

## Evidence

- `docs/contents/thesis/questions.qmd` keeps the hard thesis core on a
  target-conditioned one-step scorer, random/oracle rollouts, finite-candidate
  `Q_H`, and scale reporting.
- `.agents/memory/state/DECISIONS.md` says the learned one-step scorer is a
  myopic baseline/control and that invalidity is a hard mask/reason contract.
- `docs/contents/thesis/roadmap.qmd` places offline value learning behind masked
  Double-Q-style finite-candidate evidence and does not promote proxy rewards as
  thesis-core objectives.
- VIN-NBV, CORAL, Double DQN, CQL, IQL, SCONE, and FisherRF support the adopted
  split: root-normalized target gain owns reward/labels, ordinal calibration
  tests the one-step scorer, Double-Q controls overestimation, CQL/IQL diagnose
  support limits, and coverage/Fisher uncertainty stay auxiliary.

## Canonical Updates Needed

- Add calibration/support evaluation prose to the thesis method and evaluation
  chapters.
- Add implementation checks for one-step reliability, ordinal monotonicity,
  Double-Q overestimation, support-stratified value error, invalid firewall
  behavior, and uncertainty/reward disagreement.
- Keep CQL/IQL as controlled ablations unless the supervised and Double-Q
  baseline shows support-limited or overoptimistic failure.
