#import "../../../shared/macros.typ": *

== Candidate-View Support and Motion Feasibility <sec:thesis-candidate-support-motion-feasibility>

A finite-candidate policy selects only from the pose rows in its proposed
candidate table $cal(Q)_t = {q_(t,i)}_(i=1)^(N_t)$. PB-NBV uses a reachability-
and camera-conditioned partial hemisphere of target-facing candidates
@PB-NBV-jia2025. Proposal geometry therefore bounds what even a perfect scorer
can select.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (reachability- and camera-conditioned partial-hemisphere candidate support)

Target-relative coordinates provide a useful proposal prior without defining
the objective. PB-NBV points candidates toward the object centre, while Hestia
factorizes a viewpoint into a predicted look-at point and a camera position
@PB-NBV-jia2025 @Hestia-lu2026. Such parameterizations concentrate support on a
requested target, but an orbit or target-facing arc remains a coverage geometry,
not evidence that a wearer normally moves that way. Project Aria explicitly
contrasts carefully curated scanning motion with natural, unconstrained
egocentric activity, so wearable plausibility must be checked against trajectory
evidence rather than inferred from a target-relative construction
@projectaria-engel2023.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:38-45 (target-facing candidates on a partial hemisphere)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-123 (look-at-then-position viewpoint factorization)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/applications_new.tex:46-61 (careful scanning versus natural activity and trajectory evidence)

Geometric admissibility has at least two levels. Hestia shifts a proposed camera
position to its nearest collision-free endpoint, whereas Next Best Sense obtains
a list of feasible candidate views but still falls back to the next-ranked view
when inverse kinematics or trajectory planning fails @Hestia-lu2026
@NextBestSense-strong2024. A collision-free endpoint therefore does not by
itself establish that the transition from the current state is executable.

// evidence:
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:115-123 (nearest collision-free endpoint adjustment)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (feasible candidate list and fallback after inverse-kinematics or trajectory-planning failure)

Physical feasibility and wearable plausibility are likewise different
requirements. Robot reachability constrains PB-NBV's hemisphere, while Project
Aria supplies calibrated device trajectories recorded during natural activities
@PB-NBV-jia2025 @projectaria-engel2023. Robot-specific reachability can define a
hard admissibility test for that platform; it cannot establish a distribution
of realistic human head and body motion. For egocentric data generation, that
distribution is an empirical prior to be measured, reported, and validated.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:35-45 (robot-arm reachability and target-facing candidate support)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-24, docs/literature/tex-src/arXiv-project-aria/mps.tex:27-29, docs/literature/tex-src/arXiv-project-aria/applications_new.tex:53-61 (natural wearable capture and calibrated device trajectories)

These distinctions map the proposed poses $q_(t,i) in cal(Q)_t$ to the canonical
admissible row-index set $cal(A)(s_t) = {i : m_(t,i) = 1}$, where $m_(t,i)$ is
the hard-valid indicator after endpoint and transition checks. The utility or
value function ranks only those admitted rows;
a rejected candidate is unavailable rather than merely low-value
@PB-NBV-jia2025 @NextBestSense-strong2024. Separating proposal, admission, and
ranking makes the state dependence of available actions explicit and prepares
the sequential decision model introduced next.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70, docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (candidate generation followed by evaluation and selection)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (feasibility failures handled before final view execution)
