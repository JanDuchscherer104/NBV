#import "../../../shared/macros.typ": *
#import "_style.typ": *

= Schedule and Risk Control

The planned thesis window runs from 29 April 2026 to 30 September 2026. The
roadmap owns the detailed Gantt chart; the proposal keeps only milestone exit
conditions.

#figure(
  table(
    columns: (0.9fr, 1.15fr, 1.82fr),
    table.header([*Dates*], [*Milestone*], [*Exit condition*]),
    [2026-04-29 to 2026-05-10],
    [M0 proposal contract],
    [Proposal, roadmap, research questions, and source policy state the same finite-candidate thesis claim.],
    [2026-05-11 to 2026-05-31],
    [M1 data/oracle],
    [Offline-store, split, pose/frame, depth/backprojection, invalidity, Rerun, and throughput checks pass before target scale-up.],
    [2026-06-01 to 2026-06-21],
    [M2 one-step baseline],
    [Scene-level VIN baseline, calibration plots, LRZ sharding plan, and Zarr rollout/Q schema are ready.],
    [2026-06-22 to 2026-07-12],
    [M3 target oracle],
    [Target #RRI, V1 OBS-SEL / PRED-Q / GT-EVAL, and observed-only target selection are trusted on a small subset.],
    [2026-07-13 to 2026-08-09],
    [M4 target scorer],
    [Target-conditioned one-step scoring is compared with scene-level scoring and oracle target labels.],
    [2026-08-10 to 2026-08-30],
    [M5 headroom/$Q_H$],
    [Oracle lookahead headroom is measured; $Q_H$ is trained and oracle-evaluated if the headroom is positive.],
    [2026-08-31 to 2026-09-13],
    [M6 follow-up design],
    [Online discrete $Q_H$, IQL, actor-critic, hierarchy, and simulator paths are written as follow-up designs or post-M5 ablations.],
    [2026-09-14 to 2026-09-27],
    [M7 experiments/writing],
    [Final tables, figures, failure cases, coverage report, and thesis narrative are frozen.],
    [2026-09-28 to 2026-09-30],
    [M8 release],
    [Configs, smoke checks, demo path, and final PDF artifacts are reproducible.],
  ),
  caption: [Milestone exit criteria; the roadmap carries the full Gantt.],
) <tab:proposal-schedule>

Three risks decide interpretation. If geometry or oracle labels fail M1, the
thesis remains an oracle-contract and one-step-scoring study. If target
matching is sparse or ambiguous, target #RRI is reported only on validated
subsets with explicit unmatched counts. If $Delta_"look"$ is small, the M5
result is a falsifiable statement that the current candidate distribution is
approximately myopic; continuous RL is not promoted as a substitute result.
