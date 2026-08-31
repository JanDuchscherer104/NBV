#import "../../../shared/macros.typ": *
#import "../../../shared/tables.typ": publication-table

== Related-Work Synthesis and Research Gap <sec:thesis-related-work-synthesis>

The reviewed approaches differ along six coupled dimensions: utility, target
scope, represented evidence, representation provenance and decision-time role,
candidate support and admission, and decision horizon @SCONE-guedon2022
@FisherRF-jiang2024 @VIN-NBV-frahm2025 @PB-NBV-jia2025. Comparing only one
dimension can obscure the scientific task: a sequential coverage controller
does not answer the same question as a greedy reconstruction-quality scorer,
and neither comparison is meaningful if the relevant view lies outside
candidate support.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information-gain objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44 (greedy reconstruction-improvement ranking)
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (candidate support and target-facing proposal geometry)

#figure(
  {
    set text(size: 7.25pt)
    set par(justify: false)
    publication-table(
      text-size: 7.25pt,
      columns: (0.9fr, 1.15fr, 1.65fr, 1.3fr),
      header: ([*Family*], [*Utility and target scope*], [*State evidence and representation role*], [*Support, feasibility, and decision*]),
      rows: (
        [PB-NBV @PB-NBV-jia2025], [Projected frontier and occupied coverage; reconstruction object], [Analytic classified voxel clusters and compact projection proxies], [Reachability- and camera-conditioned partial hemisphere; greedy score],
        [3D-NVS @ThreeDNVS-ashutosh2020], [Pairwise voxel reconstruction; object], [ImageNet-pretrained VGG16 directly scores fixed next-view classes], [Eleven fixed view classes; one-step classifier],
        [SCONE / MACARONS @SCONE-guedon2022 @MACARONS-guedon2023], [Expected surface coverage; scene-wide], [Task-trained occupancy and visibility; pretrained ResNet features support MACARONS depth], [Iterative candidate selection],
        [GenNBV / Hestia @GenNBV-chen2024 @Hestia-lu2026], [Coverage gain; reconstruction object], [Task-trained geometric, history, and shallow-image encoders; Hestia uses no external pretraining], [Continuous or hierarchical policy; collision handling],
        [FisherRF @FisherRF-jiang2024], [Information gain; radiance-field scene model], [Per-scene model uncertainty enters an analytic score], [Candidate views; greedy score],
        [VIN-NBV @VIN-NBV-frahm2025], [Direct reconstruction improvement; reconstructed object], [Task-trained CNN over candidate-conditioned projections of current reconstruction], [Sampled candidates; greedy score],
        [Next Best Sense @NextBestSense-strong2024], [Color--depth information gain; radiance-field scene model], [SAM2 and depth priors support 3DGS; Fisher selection remains analytic], [Feasible candidates; fallback after kinematic or planning failure],
        [Object-centric 3DGS @ObjectCentricNBV-jeong2026], [Object-conditioned information gain; requested object], [Foundation-model masks and CLIP support object state and selection; target score remains analytic], [Candidate views; greedy score],
      ),
    )
  },
  caption: [Concept-centred comparison of the literature families that bound the thesis question. Rows are distinguished by utility, target scope, state evidence and representation role, candidate support and feasibility, and decision structure; they are not ranked by reported performance across incompatible settings.],
) <tab:thesis-related-work-synthesis>

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:155-197, docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:231-253 (projection proxies and coverage scoring)
// - @ThreeDNVS-ashutosh2020 -> docs/literature/tex-src/arXiv-3D-NVS/sections/method_new.tex:15-23 (fixed-view classifier and ImageNet-pretrained VGG16 with frozen layers)
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26, docs/literature/tex-src/arXiv-MACARONS/3_method.tex:27-34 (online coverage anticipation and pretrained ResNet-18 depth features)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (history-conditioned continuous policy and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-130 (directional state, hierarchical action, shallow encoders, and no external pretraining)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher-information view utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:101-125 (sampled candidates, RRI target, and task-trained projected-reconstruction encoder)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:156-217, docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:420-429 (SAM2/depth-supported 3DGS, Fisher selection, execution fallback, and background exploration)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/4_experiment_ver3_rpm.tex:150-160 (foundation-derived masks, analytic target score, and CLIP target selection)

Pretraining alone does not determine the scientific role of a representation.
3D-NVS uses ImageNet initialization directly in a fixed-view classifier, while
MACARONS uses pretrained image features inside an online mapping pipeline
@ThreeDNVS-ashutosh2020 @MACARONS-guedon2023. Next Best Sense places
foundation-assisted masks and depth upstream of an analytic Fisher selector
@NextBestSense-strong2024. By contrast, VIN-NBV, GenNBV, and Hestia learn their
decision state from task-specific reconstruction cues or shallow encoders
@VIN-NBV-frahm2025 @GenNBV-chen2024 @Hestia-lu2026. These approaches establish
different uses for transferred visual features, but they do not isolate the
value of an egocentric 3D representation that combines frozen 2D foundation
features with learned 3D processing for target-conditioned endpoint prediction.

// evidence:
// - @ThreeDNVS-ashutosh2020 -> docs/literature/tex-src/arXiv-3D-NVS/sections/method_new.tex:15-23 (pretrained direct fixed-view classifier)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/3_method.tex:27-34, docs/literature/tex-src/arXiv-MACARONS/7_appendix.tex:213-219 (pretrained depth features and task-specific NBV pretraining)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:156-217 (foundation-assisted scene construction with analytic selection)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:101-125, docs/literature/tex-src/arXiv-VIN-NBV/sec/8_appendix.tex:14-20 (task-trained projected-reconstruction encoder)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:29-78 (task-trained geometric, image, and action encoders)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:115-130, docs/literature/tex-src/arXiv-Hestia/sec/supp.tex:630-648 (shallow encoders and explicit absence of external pretraining)

The comparison yields two requirements for the value definition. First,
*utility alignment* requires the score to reflect the endpoint of interest:
coverage and information criteria reward proxies for reconstruction, whereas
VIN-NBV evaluates realized reconstruction error @SCONE-guedon2022
@FisherRF-jiang2024 @VIN-NBV-frahm2025. Second, *temporal dependence* requires
the score to represent delayed consequences. Sequential policies retain history
and optimize delayed reward, but the reviewed examples optimize coverage rather
than the reconstruction quality of a requested target @GenNBV-chen2024
@Hestia-lu2026. Existing work therefore establishes direct quality, target
conditioning, and sequentiality separately under different assumptions.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-quality objective)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:77-101 (history-conditioned sequential coverage policy)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (directional history and coverage reward)

A third requirement is *support/state adequacy*: valuable actions must be
available, and the causal state must retain the consequences needed to value
later actions. PB-NBV constrains proposal support; Hestia carries directional
history while separately repairing infeasible endpoints; and Next Best Sense
distinguishes feasible candidates from execution fallback @PB-NBV-jia2025
@Hestia-lu2026 @NextBestSense-strong2024. Even a perfect scorer cannot exploit a
view outside its support, and a longer horizon cannot recover a distinction
erased from the state.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (camera- and reachability-conditioned candidate support)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:115-123 (collision-free endpoint adjustment)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (fallback after inverse-kinematics or trajectory-planning failure)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (directional history and state update)

Within the actor-state question, representation transfer is a downstream
diagnostic. A pretrained carrier can help only if it preserves distinctions
aligned with target-specific return; semantic strength in 2D does not by itself
provide causal scene memory, metric support, or candidate-relative geometry.
EFM3D/EVL supplies a foundation-derived local field in which a frozen 2D feature
extractor feeds learned upsampling, 3D processing, and task heads alongside
observed surface and free-space evidence @EFM3D-straub2024. Whether that field
improves target-conditioned candidate value must therefore be measured against
matched actor-visible geometric controls after the core evidence gates, rather
than inferred from pretraining.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:4-45, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:11-18 (frozen 2D feature extraction followed by learned upsampling, 3D processing, and task heads)

This thesis studies the core requirements jointly within a bounded setting:
whether a finite-candidate policy can improve endpoint reconstruction quality
for a specified target by valuing more than the next observation. Actor-visible
foundation-derived egocentric evidence is then a conditional representation
diagnostic for the corresponding value model @VIN-NBV-frahm2025
@EFM3D-straub2024 @FixedHorizonTD-deAsis2020. Among the reviewed
reconstruction-NBV methods, none establishes this conjunction: direct-quality
prediction, target conditioning, bounded lookahead, and a matched test of a
foundation-derived egocentric representation with frozen 2D features and learned
3D processing. The literature therefore cannot determine whether non-myopic
headroom exists or whether EFM3D/EVL-derived evidence improves its recovery; the
latter remains a conditional diagnostic rather than another principal question.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-improvement precedent)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:4-45, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:11-18 (foundation-derived egocentric evidence with frozen 2D features and learned 3D processing)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (finite-horizon value construction)

The resulting principle is relational rather than architectural: view value is
defined by a target, a causal state, admissible support, a horizon, a state
update, and a continuation rule. The thesis does not generalize this bounded
relation to exhaustive novelty priority, continuous control, actor-visible
target discovery, closed-loop motion execution, or natural human movement
@GenNBV-chen2024 @Hestia-lu2026 @NextBestSense-strong2024
@projectaria-engel2023. Chapter 3 makes the bounded relation operational by
separating observable state from the privileged geometry used to construct
tasks and evaluate outcomes.

// evidence:
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (continuous sequential control setting)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (hierarchical continuous control)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (robot execution and fallback setting)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-24, docs/literature/tex-src/arXiv-project-aria/applications_new.tex:53-61 (real egocentric capture and natural-motion setting)
