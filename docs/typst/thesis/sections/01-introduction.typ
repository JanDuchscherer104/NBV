#import "../../shared/macros.typ": *
= Introduction <ch:introduction>

Active reconstruction couples sensing and inference: after a fixed acquisition budget, reconstruction quality depends not only on the surface estimator but also on which feasible viewpoints were acquired. Classical active perception therefore treats sensing actions as part of perception, and view-planning work formalizes the recurring generate--score--select loop for three-dimensional inspection @ActivePerception-bajcsy1988 @ActiveVision-aloimonos1988 @ViewPlanningSurvey-scott2003. This thesis studies a deliberately bounded instance of that problem: target-conditioned view selection from a finite admissible candidate table for egocentric indoor reconstruction.

VIN-NBV provides the closest objective precedent by supervising candidate ranking with @relative-reconstruction-improvement, computed from the reduction in point--mesh reconstruction error after adding a query view @VIN-NBV-frahm2025. ARIA-NBV retains this quality-driven principle but makes four tensions explicit: coverage or greedy selection need not equal target endpoint quality; oracle quality labels need not be actor-visible inputs; learned lookahead can exceed finite offline support; and representation capacity cannot recover evidence that the egocentric stream did not provide. The planning question is therefore bounded: does oracle lookahead improve target endpoint quality over one-step selection under the same finite candidate support, and can a learned policy use only the permitted observations? Project Aria, @aria-synthetic-environments, and @egocentric-foundation-model-3d provide the calibrated egocentric, mesh-supervised, and local actor-visible substrate for this study @projectaria-engel2023 @ProjectAria-ASE-2025 @EFM3D-straub2024.

The current data-generation tasks are defined directly from geometry-valid @ground-truth:short oriented bounding boxes. They provide target identity, target crops, and oracle labels, but they do not implement actor-visible target discovery or identity matching. Consequently, deployable-input claims require a separate observed- or predicted-target protocol; the current target tasks support oracle supervision and controlled evaluation only.

== Objectives and boundary <ssec:boundary>

The thesis objective is a finite-candidate, target-conditioned @next-best-view
comparison with equal acquisition budgets and oracle re-evaluation. The boundary
is explicit: GT geometry and meshes provide labels and evaluation only; the
actor-visible policy receives observed or predicted target descriptors and
validity masks. Claims are restricted to the sampled candidate support,
horizon, branch factor, target protocol, and held-out split.

// - repo:docs/typst/thesis/sections/01-introduction.typ:12-17
// evidence:
// claims: pc-rq1-endpoint-contract, pc-rq3-actor-oracle-separation, pc-rq4-candidate-rollout-support, pc-r0-no-confirmatory-policy-result

*Problem statement.* Given a GT-defined target task, actor-visible reconstruction evidence, a finite candidate table with hard validity constraints, and a fixed acquisition budget, determine whether bounded oracle lookahead improves endpoint target reconstruction over one-step oracle-greedy selection and, only if such headroom exists, whether a learned policy using non-privileged inputs recovers a meaningful fraction of it under the same oracle evaluation.

// - repo:docs/typst/thesis/sections/01-introduction.typ:23-23
// evidence:
// claims: pc-rq1-endpoint-contract, pc-rq2-lookahead-headroom

The thesis separates supervision from decision-time information. Ground-truth geometry defines current target tasks, target crops, oracle labels, and evaluation; it is not an ordinary actor input. Invalid candidates are outside the admissible action set rather than examples with low utility. One-step oracle greedy is an immediate-reward comparator over the evaluated valid candidate table, while oracle lookahead is an upper reference only within the fixed candidate generator, horizon, branch factor, target pool, and validity regime. These restrictions make negative results interpretable without turning a bounded experiment into a universal statement about view planning.

// - repo:docs/typst/thesis/sections/01-introduction.typ:29-29
// evidence:
// claims: pc-rq3-actor-oracle-separation, pc-rq4-candidate-rollout-support, pc-r0-no-confirmatory-policy-result

#include "01-research-questions.typ"
