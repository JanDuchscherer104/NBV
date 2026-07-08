#pagebreak()

= Appendix: VIN v2 Implementation Notes

#import "../../shared/macros.typ": *

This appendix collects implementation-level details of the VIN v2 architecture
that are too dense for the main architecture section. The goal is to keep the
main text readable while providing a precise mapping between theory and the
archived/deprecated `VinModelV2` implementation.

== Pose representation and rotation-6D

VIN v2 represents candidate poses as $#(symb.vin.T)_(#symb.frame.r <- #symb.frame.cq) in "SE"(3)$.
We encode rotation via the continuous 6D representation obtained by taking the
first two columns of the rotation matrix and flattening them into a 6-vector.
This avoids discontinuities of Euler angles and improves learning stability
@zhou2019continuity.

== Candidate-conditioned semi-dense visibility fraction

The semi-dense view conditioning uses PyTorch3D screen-space projection
(`transform_points_screen`) to decide which semi-dense points are visible from
candidate $i$. A point is considered valid if it projects to finite image
coordinates, has positive depth in the candidate camera frame, and lies within
image bounds. We define the candidate-conditioned visibility fraction

#block[
  #align(center)[
    $
      v_i^("sem") =
      (1)/(max(1, |#(symb.oracle.points)_t|))
      sum_(bold(p) in #(symb.oracle.points)_t) bb(1)["valid"_(i)(bold(p))]
    $
  ]
]

and refer to this scalar as `semidense_candidate_vis_frac` throughout the
paper. This is a proxy for how much semi-dense evidence can be reused to score
candidate $i$, even when voxel features are out-of-bounds.

== Semi-dense frustum tokens and masking

For the frustum attention block, we form tokens
$bold(tau)_(i,k) = (u, v, z, sigma_(rho), n_"obs")$ from the projected points,
where $(u, v)$ are normalized image coordinates, $z$ is depth,
$sigma_(rho)$ is inverse-distance standard deviation (`inv_dist_std`), and
$n_"obs"$ is per-point observation count (track length). We support two
candidate-dependent mechanisms:

- token-type embedding: add a learned embedding depending on whether the point
  is a valid projection,
- attention masking: optionally mask invalid tokens in cross-attention.

Both toggles are treated as ablation knobs to understand whether the model
benefits more from explicitly encoding *missing visibility* or from focusing
compute on the subset of valid projected points. These frustum-token features
are v2-only; the current VIN v3 baseline disables them unless explicitly
enabled for ablation.
