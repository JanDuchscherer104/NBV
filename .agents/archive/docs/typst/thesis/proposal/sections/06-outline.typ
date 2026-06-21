#import "../../../shared/macros.typ": *

= Preliminary Thesis Outline

The thesis will be written as an empirical methods thesis. The chapter order
mirrors the validation order so that claims are introduced only after the
corresponding contract is established.

#figure(
  table(
    columns: (0.78fr, 1.45fr, 1.58fr),
    table.header([*Chapter*], [*Purpose*], [*Expected evidence*]),
    [Introduction],
    [Motivate target-conditioned, quality-driven #NBV for egocentric indoor reconstruction and state the finite-candidate thesis claim.],
    [Research questions, contribution boundary, and source-backed scope.],
    [Background],
    [Review active perception, #NBV, #RRI, #ASE/Project Aria, EFM3D/EVL, target-aware 3DGS, and offline value learning.],
    [Literature synthesis with adoption/rejection decisions.],
    [Data and geometry contracts],
    [Describe snippets, calibration, frames, offline stores, candidates, rendered depths, backprojection, masks, and Rerun inspection.],
    [Geometry contract report, visual diagnostics, throughput, and known limitations.],
    [Oracle #RRI and target #RRI],
    [Define scene/target distances, crop matching, invalidity, and label generation.],
    [Label distributions, target crops, target/scene divergence, and failure cases.],
    [Target-conditioned scoring],
    [Present actor-visible target encoding, candidate features, VIN-style model, ordinal/regression losses, and calibration.],
    [Held-out ranking, top-$k$ oracle hit, ablations, calibration, and target-specific failures.],
    [Bounded rollout and $Q_H$],
    [Compare random-valid, one-step greedy, learned one-step scorer, oracle lookahead, temperature-softmax traces, and candidate-query $Q_H$.],
    [Cumulative target #RRI, endpoint target gain, scene #RRI, cost, invalidity, runtime, and rollout visualizations.],
    [Discussion and conclusion],
    [Interpret limits, scale blockers, simulator gaps, semantic/global planning, and real-device follow-up paths.],
    [Scope-bound conclusion and reproducibility package.],
  ),
  caption: [Preliminary thesis chapter outline.],
) <tab:proposal-outline>

The expected final contribution is a reproducible target-aware finite-candidate
view-selection study, not a broad claim that continuous reinforcement learning
has been solved for egocentric reconstruction.
