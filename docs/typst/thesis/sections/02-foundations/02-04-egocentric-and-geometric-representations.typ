#import "../../../shared/macros.typ": *
#import "../../../shared/equations.typ": eqs

== Egocentric and Geometric Representations <sec:thesis-egocentric-geometric-representations>

Project Aria supplies calibrated, time-aligned egocentric sensor streams, and
EFM3D uses posed RGB or greyscale images with semi-dense points while its boxes
and meshes provide supervision and evaluation annotations
@projectaria-engel2023 @EFM3D-straub2024. SceneScript similarly learns
structured scene descriptions from synthetic egocentric trajectories
@SceneScript-avetisyan2024. These systems define useful sensing and
representation substrates, but they do not define an NBV utility; geometry,
boxes, and counterfactual views remain oracle-side unless they are causally
derived from observations available to the actor.

// evidence:
// - @projectaria-engel2023 -> docs/literature/tex-src/arXiv-project-aria/intro.tex:24-26, docs/literature/tex-src/arXiv-project-aria/device.tex:12-15 (wearable egocentric capture and calibrated time-aligned streams)
// - @EFM3D-straub2024 -> docs/literature/tex-src/arXiv-EFM3D/intro.tex:42-50, docs/literature/tex-src/arXiv-EFM3D/dataset.tex:15-30 (posed Aria modalities, semi-dense points, boxes, and meshes)
// - @SceneScript-avetisyan2024 -> docs/literature/tex-src/arXiv-scene-script/sections/introduction.tex:14-28, docs/literature/tex-src/arXiv-scene-script/sections/dataset.tex:1-18 (structured scene representation and synthetic egocentric trajectories)

Under partial observability, a belief state is a sufficient statistic of the
action--observation history for a POMDP policy @POMDPRobotics-lauri2023.
ARIA-NBV does not claim to solve a general belief-state POMDP. Instead, its
finite actor-state representation is an empirical sufficiency hypothesis:
selected-view history and current egocentric evidence should preserve enough
information to rank the available candidates. Hestia's cumulative voxel-face
visibility state illustrates why directional observation history can matter,
but its coverage reward does not validate target-specific sufficiency
@Hestia-lu2026.

// evidence:
// - @POMDPRobotics-lauri2023 -> docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:505-505, docs/literature/tex-src/arXiv-POMDP-Robotics-Survey/root.tex:589-606 (history-dependent policies, belief-state sufficiency, and updates)
// - @Hestia-lu2026 -> docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:30-58, docs/literature/tex-src/arXiv-Hestia/sec/3_method.tex:70-93 (cumulative directional visibility and coverage reward)

The candidate table is unordered, but the output is one value per candidate.
A pooled invariant context followed by a shared row-wise map is therefore
permutation equivariant, not invariant. Deep Sets supplies the invariant
aggregation principle, while Set Transformer supplies optional
permutation-equivariant interaction among candidates. The resulting condition
is @DeepSets-zaheer2017 @SetTransformer-lee2019
$
  #eqs.rl.candidate_row_equivariance
$
This condition preserves each physical candidate's score under row
permutation; it does not require attention or any particular backbone.

// evidence:
// - @DeepSets-zaheer2017 -> docs/literature/tex-src/arXiv-Deep-Sets/nips_2017.tex:103-106 (permutation-invariant set-function decomposition)
// - @SetTransformer-lee2019 -> docs/literature/tex-src/arXiv-Set-Transformer/03_main.tex:49-65 (permutation-equivariant self-attention and invariant pooling)

Frame discipline is a separate property. QCNet uses query-centric local frames
and relative positions to reduce dependence on global coordinates
@zhou2023query. Point Transformer, KPConv, and sparse convolution represent
successively richer local point or voxel geometry, while EGNN and the
SE(3)-Transformer impose stronger equivariance through relative-coordinate or
steerable attention mechanisms @point-transformer-zhao2021 @KPConv-thomas2019
@MinkowskiEngine-choy2019 @EGNN-satorras2021 @SE3Transformer-fuchs2020. These
are challengers in an information-preservation ladder, not established
improvements for ARIA-NBV. Their value must be tested under the same causal
inputs, candidate support, and endpoint evaluation.

// evidence:
// - @zhou2023query -> docs/literature/tex-src/arXiv-QCNet/main.tex:159-161 (query-centric frames and relative positions)
// - @point-transformer-zhao2021 -> docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:21-27, docs/literature/tex-src/arXiv-Point-Transformer/tex/method.tex:55-62 (local neighborhoods and relative position encoding)
// - @KPConv-thomas2019 -> docs/literature/tex-src/arXiv-KPConv/egpaper_final.tex:75-76, docs/literature/tex-src/arXiv-KPConv/egpaper_final.tex:98-99 (point convolution with local kernel points)
// - @MinkowskiEngine-choy2019 -> docs/literature/tex-src/arXiv-MinkowskiEngine/sections/1_intro.tex:53-62 (sparse coordinates and computational savings)
// - @EGNN-satorras2021 -> docs/literature/tex-src/arXiv-EGNN/sections/model.tex:6-20, docs/literature/tex-src/arXiv-EGNN/sections/model.tex:42-60 (relative-coordinate message passing and E(n) equivariance)
// - @SE3Transformer-fuchs2020 -> docs/literature/tex-src/arXiv-SE3-Transformer/EA4PC.tex:116-127, docs/literature/tex-src/arXiv-SE3-Transformer/EA4PC.tex:143-145 (SE(3)-equivariant attention and relative positional information)
