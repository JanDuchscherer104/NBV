#import "../../../shared/macros.typ": *

== Active Perception and View Utility <sec:thesis-active-perception-utility>

Next-best-view (NBV) control couples sensing and inference through a repeated
generate--score--select loop. PB-NBV states this finite-candidate decomposition
explicitly and replaces extensive candidate ray casting with a projection-based
coverage score @PB-NBV-jia2025. The decomposition is reusable, but the score is
part of the scientific objective: sharing a candidate loop does not make two
utility functions equivalent.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24, docs/literature/tex-src/arXiv-PB-NBV/jzz_2025_ral_resub.tex:55-70 (candidate generation, utility scoring, selection, and projection-based coverage)

Four utility families recur in reconstruction-oriented NBV. Coverage and
visibility methods estimate newly observed surface, as in SCONE's volumetric
surface-coverage gain, MACARONS' online coverage anticipation, and Hestia's
voxel-face visibility memory @SCONE-guedon2022 @MACARONS-guedon2023
@Hestia-lu2026. Information and uncertainty methods instead value expected
reduction of model uncertainty; FisherRF derives such a criterion from Fisher
information for radiance fields @FisherRF-jiang2024. These objectives can be
useful baselines or features without being direct measures of reconstruction
quality.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective from occupancy and visibility fields)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26 (RGB online mapping and surface-coverage-gain anticipation)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (voxel-face visibility state and face-coverage reward)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher information and active-view information gain)

The following conceptual figure synthesizes the design axes established by
finite-candidate, coverage, uncertainty, quality-driven, and target-aware NBV
formulations @PB-NBV-jia2025 @SCONE-guedon2022 @FisherRF-jiang2024
@VIN-NBV-frahm2025 @ObjectCentricNBV-jeong2026.

// evidence:
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/related.tex:5-24 (finite-candidate NBV decomposition)
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (coverage utility)
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (information utility)
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44 (sampled candidate loop and reconstruction-improvement target)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (target-aware information gain and object-confidence gate)

#figure(
  image("../../figures/nbv_design_space_axes.pdf", width: 100%),
  caption: [Original conceptual map of the NBV design space synthesized from finite-candidate, coverage, uncertainty, quality-driven, and target-aware formulations. The diagram is a taxonomy, not an empirical result.],
) <fig:nbv-design-space-axes>

Direct quality objectives evaluate the reconstruction itself. VIN-NBV predicts
Relative Reconstruction Improvement for sampled query cameras and greedily
selects the highest predicted candidate @VIN-NBV-frahm2025. Target-specific
utility narrows this further: object-centric 3DGS view planning associates
features with Gaussian primitives and gates view utility by the requested
object @ObjectCentricNBV-jeong2026. ARIA-NBV adopts target-specific endpoint
quality as the estimand; coverage and uncertainty remain non-equivalent
diagnostics unless an experiment shows that they improve that endpoint.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (greedy candidate scoring, RRI, and ground-truth reconstruction metric)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object features, target-aware information gain, and confidence gate)
