#import "../../shared/macros.typ": *

= Introduction <ch:introduction>

Active perception begins from a geometric premise: what can be reconstructed
depends on what a sensing action makes visible @ActivePerception-bajcsy1988
@ActiveVision-aloimonos1988. A new view changes both the available surface
evidence and the state from which later views are chosen. Next-best-view (NBV)
planning turns this coupling between action, observation, and reconstruction
into the repeated choice of where to look next @ViewPlanningSurvey-scott2003
@PB-NBV-jia2025.

// evidence:
// - @ActivePerception-bajcsy1988 -> DOI 10.1109/5.5968 (local primary text unavailable; active-perception framing)
// - @ActiveVision-aloimonos1988 -> DOI 10.1007/BF00133571 (local primary text unavailable; active-vision framing)
// - @ViewPlanningSurvey-scott2003 -> DOI 10.1145/641865.641868 (local primary text unavailable; three-dimensional view-planning scope)
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (finite candidate generation, scoring, and selection)

With a limited acquisition budget, a view is “best” only relative to an
objective. Coverage rewards newly observed surface, information criteria reward
reduced uncertainty, and quality-driven methods evaluate the reconstruction
itself @SCONE-guedon2022 @FisherRF-jiang2024 @VIN-NBV-frahm2025. These objectives
can disagree. A view may reveal more of a room without exposing the occluded
surface of a requested object, while a small side-step may improve that object
but add little scene-wide coverage. Target conditioning therefore specifies
*whose geometry* should improve; it is not generic semantic awareness.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher-information view utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44,78-97 (reconstruction-quality objective, sampled candidates, and greedy selection)

Existing methods supply the necessary ingredients under different assumptions.
VIN-NBV ranks sampled candidates by direct reconstruction improvement,
object-aware 3D Gaussian Splatting conditions an information criterion on a
requested object, and GenNBV and Hestia learn sequential coverage policies
@VIN-NBV-frahm2025 @ObjectCentricNBV-jeong2026 @GenNBV-chen2024 @Hestia-lu2026.
What remains unresolved is their conjunction: whether target-specific
reconstruction quality contains useful multi-step structure and whether that
structure can be recovered from a bounded egocentric information state.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-99,122-129 (greedy RRI prediction and oracle supervision)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-268 (requested-object gating and clutter motivation)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:13-25,76-95 (history-conditioned continuous policy and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58,70-118 (sequential coverage state and hierarchical action)

Project Aria supplies calibrated egocentric observations, EFM3D lifts them into
local 3D evidence, and ARIA Synthetic Environments (ASE) provides the privileged
geometry needed for controlled target tasks and counterfactual evaluation
@projectaria-engel2023 @EFM3D-straub2024 @ProjectAria-ASE-2025. This combination
makes the information boundary testable. Task construction, action-set
construction, hard admission, supervision, and evaluation may use privileged
geometry, while the scorer consumes only the fields admitted by its declared
actor-facing protocol. Scientific interpretation must account for both paths.
Chapter 3 therefore treats actor visibility as a property of the complete
decision process, not merely of the scorer tensor.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/device.tex:12-17,71-81 (calibrated and time-aligned egocentric sensing)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:1-42 (local gravity-aligned lifting and semi-dense surface/free-space evidence)
// - @ProjectAria-ASE-2025 -> docs/contents/ase_dataset.qmd:216-225,257-260 (GT depth and meshes as supervision, oracle, and evaluation assets)
// - actor-visible and privileged information boundary -> docs/typst/thesis/sections/03-oracle-and-data-generation/03-01-state-and-visibility.typ, docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ

== Aim and bounded problem <ssec:boundary>

The thesis asks a two-stage question. First, does bounded oracle lookahead yield
better fixed-budget endpoint reconstruction of a requested object than one-step
oracle-greedy selection? Second, if such headroom exists, can an offline
finite-horizon model recover a prespecified fraction of it from non-privileged
inputs? This order separates the existence of a planning opportunity from the
ability of a learned model to exploit it.

At every step, each policy selects from the same finite generated candidates;
hard-invalid actions are excluded, and the target, horizon, candidate support,
and endpoint evaluation are matched. The current oracle tasks use
geometry-valid ground-truth boxes, while actor-visible target discovery and
matching remain separate research requirements. The objective adapts VIN-NBV
rather than copying it: VIN-NBV defines RRI from point-cloud Chamfer distance
@VIN-NBV-frahm2025, whereas ARIA-NBV evaluates a target-cropped point--mesh error
after an equal acquisition budget. The resulting claims concern this bounded
finite-candidate setting, not a deployable target-selection system or an
objective invariant to other reconstruction protocols.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44,82-92 (point-cloud Chamfer RRI precedent)
// - ARIA-NBV adaptation -> docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ:187-314 (target-cropped point--mesh error, training reward, and endpoint gain)

== Contributions and current evidence

The thesis turns this question into four scientific functions:

+ It separates one-step RRI, finite-horizon return, and fixed-budget endpoint
  gain within target-specific reconstruction quality.
+ It defines an end-to-end information boundary across task and action
  construction, state updates, model inputs, supervision, and evaluation.
+ It defines candidate value relationally over target, causal state, admissible
  action, budget, horizon, and continuation rule.
+ It evaluates measurement, support, oracle headroom, immediate-value learning,
  recursion, and endpoint recovery in that order.

// evidence:
// - measurement and information boundary -> docs/typst/thesis/sections/03-oracle-and-data-generation/
// - relational finite-horizon value -> docs/typst/thesis/sections/02-foundations/02-04-finite-horizon-value-learning.typ, docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
// - sequential evidence gates -> docs/typst/thesis/sections/05-experimental-design/

Before model capacity becomes the main question, the evidence needed to define
the learning problem must itself be identifiable. The outcome must be
repeatable, the study population and candidate support must contain the relevant
opportunity, bounded lookahead must exhibit headroom, and factual replay must
identify the required targets. Only after those conditions hold can a failure
to recover non-myopic value be attributed primarily to representation or
learning. This dependency order is the methodological spine of the thesis.

The present evidence supports a methodological contribution rather than a
policy result. The implementation executes target-specific oracle scoring and
selected-action replay, while rendering memory limits scale. Actor-visible
target matching, metric repeatability, a validated held-out population,
oracle-lookahead headroom, and paired policy outcomes remain unestablished.
Accordingly, the thesis does not yet claim policy superiority or deployment
readiness.

// evidence:
// - current evidence state -> docs/typst/thesis/sections/06-results.typ:94-123, docs/typst/thesis/sections/07-discussion.typ:12-16, docs/typst/thesis/sections/08-conclusion.typ:11-15

#include "01-research-questions.typ"

== Thesis structure <ssec:thesis-structure>

The remaining chapters follow that dependency chain. @sec:thesis-foundations
derives the objective, support, temporal, and representation concepts needed to
state the gap precisely. @sec:thesis-oracle-data-generation constructs the
experimental world by defining information access, admissible actions, state
transitions, and measured outcomes. @sec:thesis-method then specifies the one
finite-horizon value interface evaluated within that world.
@sec:thesis-experimental-design states which evidence admits or blocks each
claim. @sec:thesis-results reports the admitted answers in gate order;
@sec:thesis-discussion attributes their implications and alternatives; and
@sec:thesis-conclusion returns those bounded answers to the principal question.
