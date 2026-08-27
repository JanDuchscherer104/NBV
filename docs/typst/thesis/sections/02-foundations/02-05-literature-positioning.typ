#import "../../../shared/macros.typ": *
#import "../../../shared/tables.typ": publication-table

== Related-Work Synthesis and Research Gap <sec:thesis-related-work-synthesis>

The reviewed approaches differ along four coupled dimensions: what consequence
defines utility, whether that consequence is scene-wide or target-specific,
which evidence summarizes the acquisition history, and whether the next action
is chosen greedily or as part of a sequential policy @SCONE-guedon2022
@FisherRF-jiang2024 @VIN-NBV-frahm2025. Comparing methods along only one of
these dimensions can obscure the scientific difference. In particular, a
sequential controller with a coverage reward does not answer the same question
as a greedy scorer trained on reconstruction quality.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information-gain objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44 (greedy reconstruction-improvement ranking)

#figure(
  {
    set text(size: 7.25pt)
    set par(justify: false)
    publication-table(
      text-size: 7.25pt,
      columns: (0.95fr, 1.35fr, 1.35fr, 1.2fr),
      header: ([*Family*], [*Utility and target scope*], [*Represented evidence*], [*Decision structure*]),
      rows: (
        [PB-NBV @PB-NBV-jia2025], [Projected frontier and occupied coverage; reconstruction object], [Classified voxel clusters and compact projection proxies], [Finite proposed views; greedy score],
        [SCONE / MACARONS @SCONE-guedon2022 @MACARONS-guedon2023], [Expected surface coverage; scene-wide], [Occupancy, visibility, or online reconstruction state], [Iterative candidate selection],
        [GenNBV / Hestia @GenNBV-chen2024 @Hestia-lu2026], [Coverage gain; reconstruction object], [Observation history plus geometric or directional state], [Continuous or hierarchical sequential policy],
        [FisherRF @FisherRF-jiang2024], [Information gain; radiance-field scene model], [Model-parameter uncertainty], [Candidate views; greedy score],
        [VIN-NBV @VIN-NBV-frahm2025], [Direct reconstruction improvement; reconstructed object], [Candidate-conditioned projections of current reconstruction], [Sampled candidates; greedy score],
        [Object-centric 3DGS @ObjectCentricNBV-jeong2026], [Object-conditioned information gain; requested object], [Per-Gaussian geometry, appearance, and object confidence], [Candidate views; greedy score],
      ),
    )
  },
  caption: [Concept-centred comparison of the literature families that bound the thesis question. Rows are distinguished by utility, target scope, represented evidence, and decision structure; they are not ranked by reported performance across incompatible settings.],
) <tab:thesis-related-work-synthesis>

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:155-197, docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:231-253 (projection proxies and coverage scoring)
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26 (online coverage anticipation)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (history-conditioned continuous policy and coverage reward)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (directional state, coverage reward, and hierarchical action)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher-information view utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (sampled candidates, RRI target, and oracle reconstruction metric)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object features, target-aware information gain, and target gate)

The table exposes two tensions that motivate the thesis question. First,
coverage and information methods provide mechanisms for exploring missing or
uncertain regions, whereas VIN-NBV connects view choice directly to realized
reconstruction error @SCONE-guedon2022 @FisherRF-jiang2024
@VIN-NBV-frahm2025. Second, sequential policies represent observation history
and delayed reward, but the compared examples optimize coverage rather than
the reconstruction quality of a requested target @GenNBV-chen2024
@Hestia-lu2026. Direct quality, target conditioning, and sequentiality are
therefore established separately under different assumptions.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (coverage objective)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information objective)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-quality objective)
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:77-101 (history-conditioned sequential coverage policy)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (directional history and coverage reward)

This thesis evaluates the bounded conjunction left by those tensions: whether a
finite-candidate policy can improve endpoint reconstruction quality for a
specified target by valuing more than the next observation, using an
egocentric geometric information state @VIN-NBV-frahm2025 @EFM3D-straub2024
@FixedHorizonTD-deAsis2020. The claim is a research question, not a conclusion:
the literature motivates the combination but does not establish that the
available state is sufficient or that non-myopic headroom exists.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-improvement precedent)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33 (egocentric geometric evidence substrate)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290 (finite-horizon value construction)

The scope remains narrower than a general active-perception solution. The
comparison does not claim exhaustive novelty priority, continuous or
hierarchical control, actor-visible target discovery, or real-device deployment
@GenNBV-chen2024 @Hestia-lu2026 @projectaria-engel2023. Chapter 3 now makes the
bounded question operational by separating observable state from the privileged
geometry needed to construct target tasks and evaluate reconstruction quality.

// evidence:
// - @GenNBV-chen2024 -> docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:18-25, docs/literature/tex-src/arXiv-GenNBV/3-Method.tex:65-101 (continuous sequential control setting)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:100-118 (hierarchical continuous control)
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (real egocentric capture platform)
