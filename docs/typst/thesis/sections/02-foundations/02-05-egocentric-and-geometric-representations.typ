#import "../../../shared/macros.typ": *

== Egocentric and Geometric Representations <sec:thesis-egocentric-geometric-representations>

The preceding section established that future view value depends on a causal
information state rather than on a camera pose alone. Project Aria provides
calibrated, time-aligned egocentric streams, and EFM3D lifts posed image features
and semi-dense geometry into a local gravity-aligned representation
@projectaria-engel2023 @EFM3D-straub2024. The representation question is
therefore not how faithfully to reproduce the entire world, but which
distinctions must survive so that target-specific counterfactual return remains
predictable.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (wearable egocentric capture and calibrated time-aligned streams)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33 (posed Aria modalities and gravity-aligned voxel lifting)

Four requirements follow. First, *causal sufficiency* requires the actor state to
retain the observation history relevant to future return without importing
future or unselected evidence. EFM3D supplies strong local evidence but has a
finite voxel extent, while Hestia demonstrates that accumulated directional
history can alter later choices @EFM3D-straub2024 @Hestia-lu2026. A spatial state
is therefore not sufficient merely because it is geometric; sufficiency is a
hypothesis to be tested against the task.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (local lifted representation and finite voxel extent)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (cumulative directional visibility and coverage reward)

Second, *spatial relationality* requires the target, observer, candidates, and
observed support to be comparable in a common local geometry. Query-centric
models express scene elements relative to the active query, reducing dependence
on an arbitrary global origin @zhou2023query. For target-conditioned NBV, the
relevant relation is not candidate position in isolation but candidate geometry
relative to the current observer, target, and accumulated evidence.

// evidence:
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric local frames and relative spatial-temporal positions)

Third, *nuisance symmetry* separates transformations that should preserve a
prediction from physical quantities that should not. Translating the world
origin should not change a score, and permuting candidate rows should merely
permute their scores. Gravity, metric scale, camera direction, target
orientation, occlusion, and temporal order can nevertheless remain informative
@GeometricDeepLearning-bronstein2021 @DeepSets-zaheer2017
@SetTransformer-lee2019. The appropriate prior is disciplined equivariance, not
automatic invariance to every rigid transformation.

// evidence:
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:347-411, docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:952-967 (invariance, equivariance, locality, and geometric priors)
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set-function decomposition)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-65 (permutation-equivariant self-attention and invariant pooling)

Fourth, *physical observability* requires the representation to expose
missingness and sensing geometry rather than treating unobserved space as
negative evidence. Point, sparse-voxel, and equivariant message-passing models
offer different realizations of local geometry and symmetry
@point-transformer-zhao2021 @MinkowskiEngine-choy2019 @EGNN-satorras2021. They
are examples, not conclusions: no family is an established improvement here
until compared under the same observable inputs, target task, and endpoint
utility.

// evidence:
// - @point-transformer-zhao2021 -> docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:21-27, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:55-62 (local neighborhoods and relative position encoding)
// - @MinkowskiEngine-choy2019 -> docs/literature/tex-src/arXiv-MinkowskiEngine/sections/1_intro.tex:53-62 (sparse coordinates and computational savings)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-20, docs/literature/tex-src/arXiv-EGNN/sections/model.tex:42-60 (relative-coordinate message passing and E(n) equivariance)

These four requirements—causal sufficiency, spatial relationality, nuisance
symmetry, and physical observability—complete the conceptual dependency chain.
The literature synthesis can now compare methods by the scientific distinctions
they preserve, while the Method chapter remains responsible for one concrete
realization and its tests @EFM3D-straub2024
@GeometricDeepLearning-bronstein2021.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (causal local evidence and finite support)
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:347-411, docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricmodels.tex:463-522 (geometric priors and set-structured representations)
