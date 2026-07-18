#import "../../shared/macros.typ": *

= Introduction

Active reconstruction couples sensing and inference: after a fixed acquisition budget, reconstruction quality depends not only on the surface estimator but also on which feasible viewpoints were acquired. Classical active perception therefore treats sensing actions as part of perception, and view-planning work formalizes the recurring generate--score--select loop for three-dimensional inspection @ActivePerception-bajcsy1988 @ActiveVision-aloimonos1988 @ViewPlanningSurvey-scott2003. This thesis studies a deliberately bounded instance of that problem: target-conditioned view selection from a finite admissible candidate table for egocentric indoor reconstruction.

VIN-NBV provides the closest objective precedent by supervising candidate ranking with @relative-reconstruction-improvement, computed from the reduction in point--mesh reconstruction error after adding a query view @VIN-NBV-frahm2025. ARIA-NBV retains this quality-driven principle but changes the task and planning question. The utility is target-specific rather than scene-wide, and non-myopic value is interpreted only if bounded oracle lookahead improves endpoint quality over one-step selection under the same finite candidate support. Project Aria, @aria-synthetic-environments, and @egocentric-foundation-model-3d provide the calibrated egocentric, mesh-supervised, and local actor-visible substrate for this study @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024.

The current data-generation tasks are defined directly from geometry-valid @ground-truth:short oriented bounding boxes. They provide target identity, target crops, and oracle labels, but they do not implement actor-visible target discovery or identity matching. Consequently, deployable-input claims require a separate observed- or predicted-target protocol; the current target tasks support oracle supervision and controlled evaluation only.

*Problem statement.* Given a GT-defined target task, actor-visible reconstruction evidence, a finite candidate table with hard validity constraints, and a fixed acquisition budget, determine whether bounded oracle lookahead improves endpoint target reconstruction over one-step oracle-greedy selection and, only if such headroom exists, whether a learned policy using non-privileged inputs recovers a meaningful fraction of it under the same oracle evaluation.

The thesis separates supervision from decision-time information. Ground-truth geometry defines current target tasks, target crops, oracle labels, and evaluation; it is not an ordinary actor input. Invalid candidates are outside the admissible action set rather than examples with low utility. One-step oracle greedy is an immediate-reward comparator over the evaluated valid candidate table, while oracle lookahead is an upper reference only within the fixed candidate generator, horizon, branch factor, target pool, and validity regime. These restrictions make negative results interpretable without turning a bounded experiment into a universal statement about view planning.

== Research Questions

*RQ1 --- Objective and endpoint contract.* Do target-cropped point--mesh error, root-normalized immediate gain, and fixed-budget endpoint gain provide a repeatable objective for comparing target-conditioned view-selection policies?

*RQ2 --- Offline finite-candidate planning.* Under identical target tasks, roots, candidate support, validity rules, and acquisition budgets, does bounded oracle lookahead exhibit positive endpoint-quality headroom over one-step oracle-greedy selection, and can an offline finite-horizon policy recover a meaningful fraction of that headroom?

*RQ3 --- Actor-visible representation.* Which observed or predicted target descriptor and actor-visible state representation are sufficient for learned one-step and finite-horizon candidate scoring without privileged target geometry or all-candidate oracle renders at decision time?

*RQ4 --- Support and scale.* How do target-task coverage, candidate support, hard validity, rollout diversity, and scene-level scale constrain the reliability and generality of the conclusions for RQ1--RQ3?

Together, these questions delimit the evaluated contribution; online control, continuous actions, and real-device deployment remain outside it.
