#import "../../../shared/macros.typ": *

== Egocentric and Geometric Representations <sec:thesis-egocentric-geometric-representations>

Project Aria records calibrated, time-aligned egocentric sensor streams, and
EFM3D lifts posed image features together with semi-dense geometric evidence
into a local gravity-aligned voxel representation @projectaria-engel2023
@EFM3D-straub2024. This sensing geometry determines how observations from
different cameras and times can be compared. It does not, by itself, reveal the
complete scene or define which view is useful; an NBV representation must turn
the available evidence into relations between the current observer, the target,
and candidate viewpoints.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (wearable egocentric capture and calibrated time-aligned streams)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33 (posed Aria modalities and gravity-aligned voxel lifting)

Because the physical scene is only partially observed, representation quality
is a question of information preservation. EFM3D supplies strong local evidence
but operates over a finite voxel extent, while Hestia's cumulative voxel-face
state shows how viewing direction and observation history can change later
decisions @EFM3D-straub2024 @Hestia-lu2026. A compact state is therefore not
assumed sufficient merely because it is spatial: it must retain target identity,
observed support, directional history, and the distinctions needed to compare
future candidate consequences.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (local lifted representation and finite voxel extent)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (cumulative directional visibility and coverage reward)

Coordinate choice controls which distinctions a learner can exploit cheaply.
Query-centric models express scene elements in local frames and encode their
relations through relative positions, reducing dependence on an arbitrary
global origin @zhou2023query. Geometric deep learning generalizes this idea as a
choice of symmetries and locality priors @GeometricDeepLearning-bronstein2021.
For egocentric NBV, translation of the world origin should not change a score,
but gravity, metric scale, camera direction, target orientation, and motion can
remain meaningful. The appropriate prior is therefore disciplined relative
geometry, not automatic invariance to every rigid transformation.

// evidence:
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric local frames and relative spatial-temporal positions)
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:347-411, docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricpriors.tex:952-967 (invariance, equivariance, locality, and geometric priors)

Candidate ordering introduces another symmetry. A candidate table represents a
set of physical viewpoints, so permuting its rows should permute the associated
scores without changing their values. The required map is therefore
permutation equivariant rather than invariant. Deep Sets supplies invariant
aggregation for shared context, while Set Transformer supplies equivariant
candidate interaction @DeepSets-zaheer2017 @SetTransformer-lee2019. This is a
behavioral requirement rather than an architecture prescription: independent
row scoring, pooled context, or attention can all satisfy it if a row
permutation produces the same permutation of the output scores.

// evidence:
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set-function decomposition)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-65 (permutation-equivariant self-attention and invariant pooling)

The representation family determines how those priors are realized. Point
models preserve irregular surface samples and local relative geometry; sparse
voxel models provide structured neighborhoods without paying for a dense world
grid; equivariant message-passing models impose stronger transformation rules
@point-transformer-zhao2021 @MinkowskiEngine-choy2019 @EGNN-satorras2021. These
families trade computational structure against inductive bias. None is an
established improvement for this thesis until compared with the same observable
inputs, target task, and endpoint utility.

// evidence:
// - @point-transformer-zhao2021 -> docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:21-27, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:55-62 (local neighborhoods and relative position encoding)
// - @MinkowskiEngine-choy2019 -> docs/literature/tex-src/arXiv-MinkowskiEngine/sections/1_intro.tex:53-62 (sparse coordinates and computational savings)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-20, docs/literature/tex-src/arXiv-EGNN/sections/model.tex:42-60 (relative-coordinate message passing and E(n) equivariance)

The foundation is thus a set of representational requirements rather than an
architecture prescription: causal egocentric evidence, task-relevant spatial
relations, candidate-order equivariance, and enough history to distinguish
future consequences @EFM3D-straub2024 @GeometricDeepLearning-bronstein2021.
These requirements provide the final comparison dimension for the literature
synthesis and leave their concrete realization to the Method chapter.

// evidence:
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/method.tex:15-33, docs/literature/tex-src/arXiv-EFM3D/supplemental_text.tex:113-124 (local egocentric spatial representation and support extent)
// - @GeometricDeepLearning-bronstein2021 -> docs/literature/tex-src/arXiv-Geometric-Deep-Learning/geometricmodels.tex:463-522 (unordered-set and Euclidean geometric representation principles)
