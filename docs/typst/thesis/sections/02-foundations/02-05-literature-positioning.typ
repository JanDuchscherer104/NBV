#import "../../../shared/macros.typ": *
#import "@preview/booktabs:0.0.4": *

== Literature Positioning <sec:thesis-literature-positioning>

#figure(
  text(size: 7.45pt, table(
    columns: (0.82fr, 1.25fr, 1.18fr, 1.65fr),
    toprule(),
    table.header([*Family*], [*Utility / target*], [*Action / horizon*], [*Evidence boundary and ARIA-NBV role*]),
    midrule(),
    [PB-NBV @PB-NBV-jia2025], [Surface coverage; unknown-object reconstruction], [Finite candidates; greedy], [Reusable generate--score--select protocol; not target quality.],
    [SCONE / MACARONS / Hestia @SCONE-guedon2022 @MACARONS-guedon2023 @Hestia-lu2026], [Coverage or visibility; scene-wide], [Discrete or hierarchical acquisition], [Coverage baselines and directional-state diagnostics.],
    [FisherRF @FisherRF-jiang2024], [Information gain; scene model], [Candidate views; greedy], [Uncertainty baseline; not direct endpoint quality.],
    [VIN-NBV @VIN-NBV-frahm2025], [Reconstruction improvement; scene-wide], [Sampled candidates; greedy], [Direct quality precedent with oracle evaluation.],
    [Object-centric 3DGS @ObjectCentricNBV-jeong2026], [Object-conditioned information gain], [Candidate views; greedy], [Target-aware precedent; supplied association does not prove discovery.],
    [ARIA-NBV], [Proposed target-conditioned endpoint quality], [Finite masked candidates; explicit bounded horizon], [Proposed causal egocentric actor state under test; oracle-only supervision and endpoint evaluation.],
    bottomrule(),
  )),
  caption: [Discriminative comparison of the primary literature families that bound the thesis question. The ARIA-NBV row states the proposed evaluated conjunction, not novelty priority, implementation status, or an empirical conclusion.],
) <tab:thesis-literature-positioning>

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (finite candidate coverage selection)
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26 (online coverage anticipation)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:99-129 (visibility state, coverage reward, and hierarchical action)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher-information view utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (sampled candidates, RRI target, and oracle reconstruction metric)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object features, target-aware information gain, and target gate)

Within the reviewed families, the relevant components appear separately. The
thesis therefore evaluates a proposed conjunction: target-conditioned endpoint
reconstruction quality, finite hard-masked candidates, causal egocentric actor
evidence, an explicit finite horizon with factual successor support, and
oracle-only supervision and evaluation @VIN-NBV-frahm2025 @EFM3D-straub2024
@FixedHorizonTD-deAsis2020 @InvalidActionMasking-huang2022. This bounded
position is not an exhaustive prior-art or priority claim and excludes
continuous-control planning, actor-visible target discovery, and real-device
deployment.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (quality target and oracle reconstruction evaluation)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (egocentric actor modalities and oracle annotations)
// - @FixedHorizonTD-deAsis2020 -> docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:245-290, docs/literature/tex-src/arXiv-Fixed-Horizon-TD/AAAI-DeasisK.9337.tex:331-339 (finite-horizon recursion and Q target)
// - @InvalidActionMasking-huang2022 -> docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:66-71, docs/literature/tex-src/arXiv-Invalid-Action-Masking/formatting-instructions-latex.tex:150-174 (state-dependent admissible actions and scope)
