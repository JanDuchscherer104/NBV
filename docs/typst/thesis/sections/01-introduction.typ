#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *

= Introduction

Active reconstruction is a coupled sensing and inference problem: the reconstruction error after a fixed acquisition budget depends as much on the selected viewpoints as on the downstream surface estimator. Classical active perception treats sensing actions as part of perception itself, and view-planning surveys formalize the generate-score-select loop for three-dimensional inspection @ActivePerception-bajcsy1988 @ActiveVision-aloimonos1988 @ViewPlanningSurvey-scott2003. ARIA-NBV adopts that loop for egocentric indoor data, but asks a narrower question: when views are restricted to a finite feasible candidate table, does reconstruction-quality improvement contain planning structure beyond one-step selection?

The key empirical precedent is VIN-NBV, which replaces pure coverage with @relative-reconstruction-improvement, an oracle label computed from point-mesh reconstruction-error reduction after adding a query view @VIN-NBV-frahm2025. ARIA-NBV keeps this quality-driven axis because target indoor surfaces can remain poor even when coverage proxies look saturated. The thesis transfers this idea to the Project Aria and @aria-synthetic-environments regime, where calibrated egocentric streams, trajectories, semidense points, predicted object boxes, and mesh-supervised assets support controlled oracle labels @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024.

The implemented seminar substrate already provides scene-level oracle @relative-reconstruction-improvement:short labels and a VINv3-style one-step candidate scorer on frozen @egocentric-voxel-lifting:short features. This thesis treats that substrate as a starting point, not the final result. The extension is target-specific: oracle target-task sampling for data generation, target-cropped labels, replayable counterfactual rollouts, and a finite-horizon value model over candidate rows. V1 actor-visible claims are evaluated through observed or predicted target descriptors and @ground-truth-target-evaluation, not by giving @ground-truth:short targets to the actor.

Continuous and hierarchical @next-best-view:short papers motivate later directions, but they do not define the first thesis test. GenNBV motivates continuous policy pressure, while Hestia motivates a target-then-pose hierarchy after the finite-candidate protocol is stable @GenNBV-chen2024 @Hestia-lu2026. Active NeRF, FisherRF, Next Best Sense, semantic best-view, object-centric NBV, and FOVHPE motivate uncertainty, information, semantic, and target-aware diagnostics, but those channels are compared against the mesh-supervised @relative-reconstruction-improvement:short objective rather than replacing it @ActiveNeRF-pan2022 @FisherRF-jiang2024 @NextBestSense-strong2024 @li2025bestviewselectionssemantic @ObjectCentricNBV-jeong2026 @FOVHPE-bae2025.

#prune_todo(
  [Replace this citation parade with source-assigned research-gap prose. Keep only literature that establishes the finite-candidate, target-conditioned, quality-driven gap; route bridge methods to Related Work or Discussion.],
  source: [thesis peer review; local literature reviews],
  gate: [final introduction and related-work pass],
)

#thesis_box([Thesis position])[
  ARIA-NBV tests target-conditioned, quality-driven @next-best-view:short on @aria-synthetic-environments:short/@egocentric-foundation-model-3d:short as a finite-candidate planning problem. The core experiment first measures whether bounded oracle lookahead exposes non-myopic target-@relative-reconstruction-improvement:short headroom. If it does, a masked candidate-to-state query $Q_H$ model is evaluated by how much of that headroom it recovers from actor-visible rollout data.
]

The system object is a leakage-safe finite-candidate target-specific @relative-reconstruction-improvement:short decision process on @aria-synthetic-environments:short/@egocentric-voxel-lifting:short. Given an @aria-synthetic-environments:short snippet, an oracle-sampled target task, a finite valid candidate set, and a fixed horizon, ARIA-NBV measures target-specific point-mesh @relative-reconstruction-improvement:short, estimates non-myopic headroom by oracle lookahead, and learns #symb.rl.qh from non-privileged state and target-task descriptors to recover that headroom. The learned state-action value model induces the finite-action policy $pi_Q$.

The contribution is fourfold: a leakage-safe target-specific @relative-reconstruction-improvement:short protocol, a headroom-measured finite-candidate planning test, a geometry-aware uncentred residual #symb.rl.qh value model, and support-aware rollout generation. The validation sequence follows that order: target-specific @relative-reconstruction-improvement:short label construction, a calibrated target-conditioned one-step scorer over potential counterfactual views, oracle-lookahead headroom, and continuous-return residual #symb.rl.qh over finite valid candidates.

#impl_todo(
  [Rewrite the contribution statement from implemented, evaluated outputs. The current fourfold list includes M4/M5 method and rollout objectives that are not yet established contributions. Map every retained contribution to a final method section and result table.],
  source: [thesis roadmap; current results scaffold; thesis peer review],
  gate: [final implementation and result freeze],
)

#question_todo(
  [Add the final explicit research questions and scoped hypotheses here. The thesis-position box is useful orientation, but it does not replace a numbered, testable RQ block tied to the evaluation protocol.],
  source: [docs/contents/thesis/questions.qmd; thesis section contract],
  gate: [research-question freeze],
)

#decision_todo(
  [The thesis title, exact RQ wording, and final evidence scale must be re-locked once M5 evidence is known.],
  source: [proposal sections; advisor handout],
  gate: [pre-submission thesis freeze],
)
