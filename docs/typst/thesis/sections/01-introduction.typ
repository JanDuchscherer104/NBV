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

Existing methods resolve different parts of this problem. VIN-NBV greedily
ranks sampled candidates by Relative Reconstruction Improvement
@VIN-NBV-frahm2025. Object-aware 3D Gaussian Splatting conditions an information
criterion on the requested object @ObjectCentricNBV-jeong2026. GenNBV and Hestia
learn sequential coverage policies in continuous or hierarchical action spaces
@GenNBV-chen2024 @Hestia-lu2026. The literature reviewed in this thesis thus
provides direct reconstruction-quality scoring, target-aware utility, and
sequential view selection under different assumptions. It does not establish
their conjunction: whether target-specific reconstruction quality contains
useful multi-step structure that can be recovered from a bounded egocentric
information state.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-99,122-129 (greedy RRI prediction and oracle supervision)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-268 (requested-object gating and clutter motivation)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:13-25,76-95 (history-conditioned continuous policy and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58,70-118 (sequential coverage state and hierarchical action)

Project Aria supplies calibrated egocentric observations
@projectaria-engel2023, and EFM3D lifts such observations into local 3D evidence
@EFM3D-straub2024. ARIA Synthetic Environments (ASE) adds the privileged
geometry needed to construct controlled target tasks and evaluate
counterfactual actions @ProjectAria-ASE-2025. This setting permits a strict
deployable-path separation: the actor-visible path may use logged and causally
derived observations, whereas ground-truth geometry, unselected renders, and
reconstruction labels remain task-construction, supervision, or evaluation
assets. Two explicitly non-deployable controls remain separate: the GT-target
control supplies privileged target geometry, and the `CF-GT` selected-depth
ablation may consume previously selected GT depth. Neither can support a
deployable-input claim.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/device.tex:12-17,71-81 (calibrated and time-aligned egocentric sensing)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:1-42 (local gravity-aligned lifting and semi-dense surface/free-space evidence)
// - @ProjectAria-ASE-2025 -> docs/contents/ase_dataset.qmd:216-225,257-260 (GT depth and meshes as supervision, oracle, and evaluation assets)
// - deployable and privileged input boundary -> docs/typst/thesis/sections/04-method/04-01-scene-representation-requirements.typ:19-23, docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ:24-40, docs/typst/thesis/sections/04-method/04-04-architecture-contract.typ:39-43

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

The thesis turns this question into an auditable chain from objective to
evidence:

+ It distinguishes state-relative one-step RRI, an additive finite-horizon
  training return, and fixed-budget endpoint gain so that training signals and
  policy outcomes are not conflated.
+ It defines finite target-task, candidate, label, and replay contracts that
  preserve lineage, treat invalidity as a hard constraint, and keep actor inputs
  separate from oracle-only assets.
+ It specifies masked finite-horizon candidate scoring from target context,
  causal history, remaining budget, and requested horizon.
+ It predefines a scene-disjoint, matched-budget evaluation that first tests
  oracle-lookahead headroom and only then measures learned recovery, while
  reporting feasibility separately from policy performance.

// evidence:
// - objective and oracle contracts -> docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ:15-32,257-314
// - method status and interface -> docs/typst/thesis/sections/04-method/index.typ:13-17, docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ:14-24,42-92
// - evaluation contract -> docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ:15-54, docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ:15-37

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

The remaining chapters follow the same dependency chain. @sec:thesis-foundations
derives the view-utility, target-conditioning, sequential-decision, and
geometric-representation concepts that define the research gap.
@sec:thesis-oracle-data-generation turns that gap into data by separating
actor-visible state from privileged task construction, oracle evaluation, and
counterfactual replay. @sec:thesis-method specifies the finite-candidate scorer,
its geometric inputs, masks, and finite-horizon learning interface.
@sec:thesis-experimental-design defines the study population, evidence gates,
baselines, and matched endpoint comparisons. @sec:thesis-results reports only
the evidence admitted by those contracts. @sec:thesis-discussion interprets
that evidence, alternative explanations, and limitations, and
@sec:thesis-conclusion answers the research questions within the established
scope.
