#import "../../../shared/macros.typ": *

== Active Perception and the Next-Best-View Problem <sec:thesis-active-perception-nbv>

In active perception, an observation is also an intervention on the future
information state. A next-best-view (NBV) method operationalizes this idea by
generating possible viewpoints, estimating the benefit of observing from each
one, and selecting an action. PB-NBV makes this generate--score--select
decomposition explicit for a finite candidate set @PB-NBV-jia2025. The
decomposition identifies three different scientific objects: the proposal
mechanism determines which views can be considered, the utility determines how
they are ordered, and the selection rule turns that ordering into an action.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (candidate generation, utility scoring, selection, and projection-based coverage)

How those objects are represented varies across NBV systems. Finite-candidate
methods evaluate a bounded set of poses, whereas learned continuous policies
predict camera position and orientation directly. GenNBV formulates the latter
as a five-degree-of-freedom reinforcement-learning problem, while Hestia
factorizes the continuous action into a look-at point followed by a camera
position @GenNBV-chen2024 @Hestia-lu2026. A finite set makes the evaluated
choices explicit and comparable; a continuous or hierarchical policy can
search a broader space but couples view proposal and control more tightly.

// evidence:
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:5-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-78 (sequential MDP formulation, historical observations, and continuous five-DoF action)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/1_intro.tex:21-42, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (continuous viewpoint and hierarchical look-at-then-position action)

These action formulations do not determine what makes a view useful. PB-NBV,
for example, accelerates candidate evaluation through projected frontier and
occupied evidence, so its proposal and scoring mechanism is tied to a coverage
objective @PB-NBV-jia2025. The same finite candidate table could instead be
ranked by uncertainty reduction or by reconstruction error. Consequently,
changing the utility changes the scientific task even when candidate generation
and selection remain unchanged.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:155-197, docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:231-253 (projection-based frontier and occupied-evidence score)

The NBV mechanism therefore answers only *how* a sensing choice is made. To
interpret the choice, the utility must state *which reconstruction consequence*
is valued and *for which spatial support*. This distinction leads from the
general active-perception loop to the objective families compared next
@PB-NBV-jia2025 @GenNBV-chen2024.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24 (finite-candidate NBV stages)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:5-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:77-101 (sequential action and coverage-reward formulation)
