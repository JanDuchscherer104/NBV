#import "../../../shared/macros.typ": *
#import "../../../shared/tables.typ": publication-table

== Related-Work Synthesis and Research Gap <sec:thesis-related-work-synthesis>

The reviewed approaches differ along five coupled dimensions: utility, target
scope, represented evidence, candidate support and admission, and decision
horizon @SCONE-guedon2022 @FisherRF-jiang2024 @VIN-NBV-frahm2025
@PB-NBV-jia2025. Comparing only one dimension can obscure the scientific task:
a sequential coverage controller does not answer the same question as a greedy
reconstruction-quality scorer, and neither comparison is meaningful if the
relevant view lies outside candidate support.

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
      columns: (0.9fr, 1.25fr, 1.25fr, 1.45fr),
      header: ([*Family*], [*Utility and target scope*], [*Represented evidence*], [*Support, feasibility, and decision*]),
      rows: (
        [PB-NBV @PB-NBV-jia2025], [Projected frontier and occupied coverage; reconstruction object], [Classified voxel clusters and compact projection proxies], [Reachability- and camera-conditioned partial hemisphere; greedy score],
        [SCONE / MACARONS @SCONE-guedon2022 @MACARONS-guedon2023], [Expected surface coverage; scene-wide], [Occupancy, visibility, or online reconstruction state], [Iterative candidate selection],
        [GenNBV / Hestia @GenNBV-chen2024 @Hestia-lu2026], [Coverage gain; reconstruction object], [Observation history plus geometric or directional state], [Continuous or hierarchical policy; collision handling],
        [FisherRF @FisherRF-jiang2024], [Information gain; radiance-field scene model], [Model-parameter uncertainty], [Candidate views; greedy score],
        [VIN-NBV @VIN-NBV-frahm2025], [Direct reconstruction improvement; reconstructed object], [Candidate-conditioned projections of current reconstruction], [Sampled candidates; greedy score],
        [Next Best Sense @NextBestSense-strong2024], [Color--depth information gain; radiance-field scene model], [3DGS uncertainty and multimodal observations], [Feasible candidates; fallback after kinematic or planning failure],
        [Object-centric 3DGS @ObjectCentricNBV-jeong2026], [Object-conditioned information gain; requested object], [Per-Gaussian geometry, appearance, and object confidence], [Candidate views; greedy score],
      ),
    )
  },
  caption: [Concept-centred comparison of the literature families that bound the thesis question. Rows are distinguished by utility, target scope, represented evidence, candidate support and feasibility, and decision structure; they are not ranked by reported performance across incompatible settings.],
) <tab:thesis-related-work-synthesis>

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:155-197, docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:231-253 (projection proxies and coverage scoring)
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26 (online coverage anticipation)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (history-conditioned continuous policy and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (directional state, coverage reward, and hierarchical action)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher-information view utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (sampled candidates, RRI target, and oracle reconstruction metric)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:190-217, docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:420-429 (scene-model color-depth information gain, feasible candidate views, execution fallback, and background exploration)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object features, target-aware information gain, and target gate)

The comparison exposes three tensions. The *objective tension* is that coverage
and information criteria reward proxies for reconstruction, whereas VIN-NBV
evaluates realized reconstruction error @SCONE-guedon2022 @FisherRF-jiang2024
@VIN-NBV-frahm2025. The *temporal tension* is that sequential policies represent
history and delayed reward, but the reviewed examples optimize coverage rather
than the reconstruction quality of a requested target @GenNBV-chen2024
@Hestia-lu2026. Direct quality, target conditioning, and sequentiality are thus
established separately under different assumptions.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-quality objective)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:77-101 (history-conditioned sequential coverage policy)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (directional history and coverage reward)

The *support/state tension* is that a sequential objective is meaningful only
relative to the actions that can be proposed and the causal information retained
after acting. PB-NBV constrains proposal support, Hestia changes the state through
directional history and endpoint repair, and Next Best Sense separates feasible
candidates from execution fallback @PB-NBV-jia2025 @Hestia-lu2026
@NextBestSense-strong2024. Even a perfect scorer cannot exploit a view outside
its support, and a longer horizon cannot recover a distinction erased from the
state.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (camera- and reachability-conditioned candidate support)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:115-123 (collision-free endpoint adjustment)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (fallback after inverse-kinematics or trajectory-planning failure)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (directional history and state update)

This thesis evaluates the bounded conjunction left by those tensions: whether a
finite-candidate policy can improve endpoint reconstruction quality for a
specified target by valuing more than the next observation, using an egocentric
geometric information state @VIN-NBV-frahm2025 @EFM3D-straub2024
@FixedHorizonTD-deAsis2020. No reviewed work establishes that conjunction, and
the literature cannot establish that the available actor state is sufficient or
that non-myopic headroom exists in this setting. Those remain the empirical
questions of the thesis.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-improvement precedent)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33 (egocentric geometric evidence substrate)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (finite-horizon value construction)

The resulting principle is relational rather than architectural: view value is
defined by a target, a causal state, admissible support, a horizon, a state
update, and a continuation rule. The thesis does not generalize this bounded
relation to exhaustive novelty priority, continuous control, actor-visible
target discovery, closed-loop motion execution, or natural human movement
@GenNBV-chen2024 @Hestia-lu2026 @NextBestSense-strong2024
@projectaria-engel2023. Chapter 3 now makes the bounded relation operational by
separating observable state from the privileged geometry used to construct
tasks and evaluate outcomes.

// evidence:
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (continuous sequential control setting)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (hierarchical continuous control)
// - @NextBestSense-strong2024 -> docs/literature/tex-src/arXiv-Next-Best-Sense/ms.tex:211-217 (robot execution and fallback setting)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-24, docs/literature/tex-src/arXiv-project-aria/applications_new.tex:53-61 (real egocentric capture and natural-motion setting)
