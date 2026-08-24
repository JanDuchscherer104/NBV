# Thesis Section Contracts

Use these acceptance checks when drafting or reviewing thesis/proposal prose.

## Introduction

Must contain concrete problem context, the target-aware NBV gap, the ARIA-NBV
contribution, scope boundaries, and testable research questions. Reject if
semantic relevance is a slogan or contributions are generic.

## Related Work

Each paragraph names a subfield, states what prior work contributes, identifies
the limitation relative to ARIA-NBV, and cites specific sources. Avoid "many
works have explored" openings and unassigned citation clusters.

## System / Method

Must state inputs, actor-visible state, oracle-only assets, finite candidate
set, masks/reasons, target protocol, equations, learned components, and
expected failure modes. Reject if GT assets appear actor-visible without an
explicit V0/upper-bound label.

## Offline Oracle

Must separate label generation from decision-time inputs, define the metric,
state invalidity as a hard constraint, and name where evaluation uses GT.
Reject if invalid candidates are treated as merely low reward.

## VIN Proxy / One-Step Scorer

Must define the myopic task, target conditioning, baseline role, evidence
needed for calibration, and what the scorer is not allowed to claim.

## Finite-Horizon Q_H

Must define the finite candidate action space, masked candidate-token output,
training return, endpoint metric, oracle re-evaluation, and headroom condition.
Reject if planned `Q_H` behavior is phrased as implemented evidence.

## Experiments

Must specify dataset/splits, candidate sampling, baselines, ablations, metrics,
aggregation, runtime/coverage reporting, and threats to validity.

## Limitations And Conclusion

Must separate established results, design implications, blockers, bridge work,
and future work. Reject if continuous control, real-device deployment, or
semantic global planning is promoted beyond available evidence.
