#import "../../../shared/macros.typ": *
#import "_style.typ": *

= Motivation

Active reconstruction is a coupled sensing and inference problem: the
reconstruction error after a fixed budget depends as much on the selected
viewpoints as on the downstream surface estimator. Classical active perception
therefore treats sensing actions as part of perception itself, and view-planning
surveys formalize the dominant generate-score-select loop for three-dimensional
inspection @ActivePerception-bajcsy1988 @ActiveVision-aloimonos1988
@ViewPlanningSurvey-scott2003. ARIA-NBV adopts that loop for egocentric indoor
data, but asks a narrower question: when views are restricted to a finite
feasible candidate table, does reconstruction-quality improvement contain
planning structure beyond one-step selection?

The key empirical precedent is VIN-NBV, which replaces pure coverage with
#gls("relative-reconstruction-improvement"), an oracle label computed from
point-mesh reconstruction-error reduction after adding a query view
@VIN-NBV-frahm2025. ARIA-NBV uses the same quality-driven axis because target
indoor surfaces can remain poor even when coverage proxies look saturated. The
thesis transfers this idea to the Project Aria / #gls("aria-synthetic-environments") regime, where calibrated
egocentric streams, trajectories, semi-dense points, predicted object boxes,
and mesh-supervised assets support controlled oracle labels
@projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024.

The implemented seminar substrate already provides scene-level oracle #RRI
labels and a VINv3-style one-step candidate scorer on frozen EVL features. This
proposal treats that as the starting point, not the final thesis result. The
extension is target-specific: actor-visible target selection, target-cropped
oracle labels, replayable counterfactual rollouts, and a finite-horizon value
model over candidate rows.

Continuous and hierarchical #gls("next-best-view") papers motivate later directions, but they do
not define the first thesis test. GenNBV and Hestia assume mature simulator
dynamics and reward loops @GenNBV-chen2024 @Hestia-lu2026; active NeRF and 3DGS
work motivates utility-channel diagnostics rather than replacing the
mesh-supervised #RRI objective @ActiveNeRF-pan2022 @FisherRF-jiang2024
@NextBestSense-strong2024 @li2025bestviewselectionssemantic
@ObjectCentricNBV-jeong2026 @FOVHPE-bae2025.

#thesis-box([Thesis position])[
  ARIA-NBV tests target-conditioned, quality-driven #gls("next-best-view", first: false) on #gls("aria-synthetic-environments", first: false)/EFM as a
  finite-candidate planning problem. The core experiment first measures whether
  bounded oracle lookahead exposes non-myopic target-#RRI headroom. If it does,
  a masked candidate-query $Q_H$ model is evaluated by how much of that headroom
  it recovers from actor-visible rollout data.
]
