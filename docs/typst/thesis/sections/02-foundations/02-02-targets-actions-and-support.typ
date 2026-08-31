#import "../../../shared/macros.typ": *

== View Utility and Target-Conditioned Reconstruction <sec:thesis-view-utility-target-conditioning>

Coverage-based utilities value evidence about previously unobserved surface.
SCONE estimates surface-coverage gain from occupancy and visibility fields,
MACARONS anticipates coverage gain while reconstructing online, and Hestia
rewards newly visible voxel faces @SCONE-guedon2022 @MACARONS-guedon2023
@Hestia-lu2026. These objectives connect a view to geometric completeness, but
they weight every counted surface element through the coverage definition; they
do not directly ask whether the reconstructed geometry became more accurate.

// evidence:
// - @SCONE-guedon2022 -> docs/literature/tex-src/arXiv-SCONE/camera_ready_1_intro.tex:24-26 (surface-coverage objective from occupancy and visibility fields)
// - @MACARONS-guedon2023 -> docs/literature/tex-src/arXiv-MACARONS/1_introduction.tex:13-26 (online mapping and surface-coverage-gain anticipation)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (cumulative voxel-face visibility and coverage reward)

Information-based utilities instead value a view through its expected reduction
of model uncertainty. FisherRF derives an information-gain criterion from the
Fisher information of a radiance field @FisherRF-jiang2024. Such a criterion can
prefer a view that constrains uncertain model parameters even when its immediate
surface coverage is small. The benefit is model-aware exploration; the
limitation is that lower parameter uncertainty and lower geometric
reconstruction error are related only through assumptions about the model and
the evaluated scene.

// evidence:
// - @FisherRF-jiang2024 -> docs/literature/tex-src/arXiv-FisherRF/sec/method.tex:4-19 (Fisher information and active-view information gain)

Direct quality utilities close this proxy gap by evaluating the reconstruction
itself. VIN-NBV defines Relative Reconstruction Improvement (RRI) as the
reduction in Chamfer distance between reconstructed and ground-truth point
clouds after adding a candidate observation, and learns to rank sampled query
cameras by this quantity @VIN-NBV-frahm2025. The present work follows this
direct reconstruction-improvement principle but not VIN-NBV's metric unchanged:
it evaluates a target-cropped point--mesh error instead of scene-level
point-cloud Chamfer distance. This project-specific definition makes the
requested target, rather than all reconstructed geometry, determine which
errors count. It does not remove the myopia of one-step scoring, because each
candidate is still valued by its immediate improvement rather than by the
sequence it may enable.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:18-20, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (sampled candidate scoring and point-cloud Chamfer RRI)

Target conditioning changes which reconstruction errors contribute to that
quality. Object-centric 3DGS planning associates features and confidence with
individual Gaussian primitives and gates its information score by the requested
object @ObjectCentricNBV-jeong2026. This mechanism demonstrates that a view can
be informative for one object without being equally useful for the scene as a
whole. It also exposes a separate assumption: supplying an object identifier or
region for conditioning is not the same problem as discovering that object and
maintaining its identity from observations.

// evidence:
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:54-86, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object-associated features, target-aware information gain, and requested-object gate)

The thesis therefore treats coverage and uncertainty as non-equivalent
diagnostics and adopts target-specific reconstruction quality as the endpoint
of interest @VIN-NBV-frahm2025 @ObjectCentricNBV-jeong2026. These works motivate
direct reconstruction improvement and object conditioning separately; their
combination in a target-cropped endpoint is the thesis-specific objective. This
choice determines what the decision should improve, but not which viewpoints
may be proposed or reached. Candidate support and motion feasibility therefore
remain separate from utility before delayed consequences are introduced through
the finite-horizon decision problem @PB-NBV-jia2025.

// evidence:
// - @VIN-NBV-frahm2025 -> docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:36-44, docs/literature/tex-src/arXiv-VIN-NBV/sec/3_methods.tex:78-92 (direct reconstruction-improvement target and evaluation)
// - @ObjectCentricNBV-jeong2026 -> docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:123-139, docs/literature/tex-src/arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex:249-258 (object-conditioned view utility)
// - @PB-NBV-jia2025 -> docs/literature/tex-src/arXiv-PB-NBV/sections/method.tex:21-45 (candidate support set independently of its later score)
