#import "../../shared/macros.typ": *
#import "../draft_markers.typ": *

= Introduction

Active reconstruction couples sensing and inference: after a fixed acquisition budget, reconstruction quality depends not only on the surface estimator but also on which feasible viewpoints were acquired. Classical active perception therefore treats sensing actions as part of perception, and view-planning work formalizes the recurring generate--score--select loop for three-dimensional inspection @ActivePerception-bajcsy1988 @ActiveVision-aloimonos1988 @ViewPlanningSurvey-scott2003. This thesis studies a deliberately bounded instance of that problem: target-conditioned view selection from a finite admissible candidate table for egocentric indoor reconstruction.

VIN-NBV provides the closest objective precedent by supervising candidate ranking with @relative-reconstruction-improvement, computed from the reduction in point--mesh reconstruction error after adding a query view @VIN-NBV-frahm2025. ARIA-NBV retains this quality-driven principle but changes the task and planning question. The task is target-specific rather than only scene-wide; the actor operates from logged or counterfactually updated actor-visible evidence; and non-myopic value is tested only after a matched finite-candidate oracle comparison establishes measurable headroom. Project Aria, @aria-synthetic-environments, and @egocentric-foundation-model-3d provide the calibrated egocentric, mesh-supervised, and actor-visible substrate for that study @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024.

#thesis_box([Problem statement])[
  Given an oracle-defined target task, an actor-visible target descriptor, an actor-visible reconstruction state, a finite candidate table with hard validity constraints, and a fixed acquisition budget, determine whether bounded oracle lookahead improves endpoint target reconstruction over one-step oracle-greedy selection and, only if such headroom exists, whether an actor-visible learned policy recovers a meaningful fraction of it under the same oracle evaluation.
]

The thesis separates supervision from decision-time information. Ground-truth geometry defines target identity, target crops, oracle labels, matching, and evaluation. It is not an ordinary actor input. Invalid candidates are outside the admissible action set rather than examples with low utility. One-step oracle greedy is an immediate-reward comparator over the evaluated valid candidate table, while oracle lookahead is an upper reference only within the fixed candidate generator, horizon, branch factor, target pool, and validity regime. These restrictions make negative results interpretable without turning a bounded experiment into a universal statement about view planning.

== Research Questions

*RQ1 --- Objective and endpoint contract.* Does the target-cropped point--mesh error, its root-normalized immediate gain, and fixed-budget endpoint gain form a repeatable and scientifically valid objective for comparing target-conditioned view-selection policies?

*RQ2 --- Offline finite-candidate planning.* Under matched targets, roots, candidate support, validity rules, and acquisition budgets, does bounded oracle lookahead exhibit positive endpoint-quality headroom over one-step oracle-greedy selection, and can an offline actor-visible finite-horizon policy recover a meaningful fraction of that headroom?

*RQ3 --- Actor-visible target and state representation.* Which actor-visible target descriptor and state representation are sufficient for learned one-step and finite-horizon candidate scoring without privileged target geometry or all-candidate oracle renders at decision time?

*RQ4 --- Support and scale.* How do candidate support, hard validity, rollout diversity, target coverage, and scene-level scale constrain the reliability and generality of the conclusions for RQ1--RQ3?

*Conditional RQ5 --- Online discrete bridge.* If the offline finite-candidate protocol establishes valid metrics, positive headroom, and learned recovery, does online interaction over the same discrete candidate contract improve robustness or data efficiency?

*Conditional RQ6 --- Continuous-control bridge.* If the discrete protocol is stable and its limitations are attributable to candidate support, can a continuous or hierarchical controller improve endpoint target quality without weakening the actor/oracle and matched-evaluation contracts?

RQ5 and RQ6 are bridge questions, not thesis-core contributions. They remain outside the confirmatory claim set unless the preceding evidence gates are satisfied.

== Research Objectives

The first objective is to define and validate a leakage-safe target-task and reconstruction-quality contract. The second is to measure finite-candidate non-myopic headroom under matched budgets and admissible actions. The third is to specify actor-visible one-step and finite-horizon learning problems whose selected actions can be re-evaluated by the same oracle. The fourth is to quantify the support, validity, coverage, and scale conditions under which those comparisons are meaningful. These are research objectives; they become achieved contributions only where the Results chapter supplies frozen evidence.

#validation_todo(
  [Convert only evidence-backed objectives into final contribution claims and map each retained claim to a result table, uncertainty interval, and stated limitation.],
  source: [final results and claim ledger],
  gate: [submission claim freeze],
)
