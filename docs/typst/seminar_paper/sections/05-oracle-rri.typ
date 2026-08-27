= Oracle RRI Computation <sec:oracle-rri>

#import "../../shared/macros.typ": *
#import "../../shared/tables.typ": publication-table

// NOTE(paper-cleanup): Treat this as the single “ground truth” description of the oracle
// pipeline. Remove or shorten duplicated pipeline explanations in other sections and refer
// here (esp. Problem Formulation, Coordinate Conventions, and Evaluation).

// Single source of truth for the numeric parameters shown in this section.
// Keep this in sync with the slide deck, which imports the same config.
#let oracle_cfg_src = "/typst/shared/data/paper_figures_oracle_labeler.toml"
#let oracle_cfg = toml(oracle_cfg_src)
#let dataset_cfg = oracle_cfg.dataset
#let labeler_cfg = oracle_cfg.labeler
#let gen_cfg = labeler_cfg.generator
#let depth_cfg = labeler_cfg.depth
#let renderer_cfg = depth_cfg.renderer

Oracle RRI labels are computed offline by rendering candidate depth maps from
ground-truth meshes and fusing these points with the current reconstruction.
The pipeline is implemented with PyTorch3D rasterization and EFM3D utilities
for unprojection, point fusion, and Chamfer evaluation.

#figure(
  image("/figures/diagrams/oracle_rri/oracle_rri_compact.pdf", width: 100%),
  caption: [Oracle RRI pipeline (offline labeling).],
) <fig:oracle-rri-pipeline>

== Inputs and outputs

The oracle labeler consumes one ASE-EFM snippet (see @sec:dataset) and produces
per-candidate oracle scores and auxiliary diagnostics. Concretely, the input
provides:

- the trajectory #symb.ase.traj and final reference pose #symb.ase.traj_final,
- the semi-dense reconstruction point set $#(symb.oracle.points) _t$ derived from
  #symb.ase.points_semi as described in @sec:dataset,
- the ground-truth mesh surface #symb.ase.mesh (triangles #symb.ase.faces) for
  the mesh subset described in @sec:dataset,
- camera intrinsics/extrinsics (used to build candidate cameras).

The output is a set of candidate poses #symb.oracle.candidates and oracle labels
(`RRI`, plus accuracy/completeness components), optionally followed by ordinal
binning for CORAL training.

For efficiency, we preprocess the GT mesh #symb.ase.mesh at most once per
snippet: we optionally crop it to snippet bounds and simplify it via quadric
decimation, then cache the processed mesh for reuse across collision checks and
depth rendering (see #gh("aria_nbv/aria_nbv/data/mesh_cache.py")).

The end-to-end oracle labeler is implemented in
#gh("aria_nbv/aria_nbv/oracle/pipelines/scene_labels.py").

== Candidate generation

Given the reference rig pose #T(symb.frame.w, symb.frame.r) at the final
trajectory time step, we sample #symb.shape.Nq candidate camera poses in a
constrained shell around the reference and prune invalid proposals.

#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Key parameters (candidate generation).],
  [
    #let gen_rows = (
      ([$#symb.shape.Nq$], [#gen_cfg.num_samples]),
      ([$r_"min"$], [#gen_cfg.min_radius]),
      ([$r_"max"$], [#gen_cfg.max_radius]),
      ([$theta_"min"$], [#gen_cfg.min_elev_deg]),
      ([$theta_"max"$], [#gen_cfg.max_elev_deg]),
      ([$psi_"span"$], [#gen_cfg.delta_azimuth_deg]),
      ([$psi_delta$], [#gen_cfg.view_max_azimuth_deg]),
      ([$theta_delta$], [#gen_cfg.view_max_elevation_deg]),
      ([$phi_delta$], [#gen_cfg.view_roll_jitter_deg]),
      (code-inline("align_to_gravity"), [#gen_cfg.align_to_gravity]),
      (code-inline("min_dist_to_mesh"), [#gen_cfg.min_distance_to_mesh]),
    )
    #let gen_cells = gen_rows.flatten()
    #publication-table(
      columns: (14em, auto),
      header: ([Setting], [Value]),
      align: (left, left),
      rows: gen_cells,
    )
  ],
) <tab:oracle-cfg-candgen>

=== Candidate center sampling (position sampling)

Candidate centers are sampled by drawing a direction $bold(s)_q$ on the unit
sphere $bb(S)^2 subset bb(R)^3$ and a radius $r_q in (r_"min", r_"max")$, then
rescaling the direction into $(psi, theta)$ caps *without rejection* (see
#gh("aria_nbv/aria_nbv/pose_generation/positional_sampling.py")).

Here $bold(s)_q in bb(S)^2$ is a unit direction parameterized in spherical
coordinates by azimuth $psi$ and elevation $theta$.

#block[
  #align(center)[
    $
      bold(s)_q ~ cal(U)(bb(S)^2),
      quad
      r_q ~ cal(U)(r_"min", r_"max")
    $
  ]
]

We draw directions either uniformly, or from a forward-biased Power Spherical
distribution centered at the device forward axis
$bold(s)_q ~ "PS"(bold(mu), kappa)$ @PowerSpherical-deCao2020.

Gravity-aligned sampling uses #T(symb.frame.w, symb.frame.s) (roll/pitch
removed). #T(symb.frame.w, symb.frame.r) is the reference pose rotation; the
angles $(psi, theta)$ only parameterize the direction $bold(s)_q in bb(S)^2$:

#block[
  #align(center)[
    $
      (psi, theta) = "angles"(bold(s)_q) \
      (psi, theta) <- "lin"([psi_"min", psi_"max"] times [theta_"min", theta_"max"]; (psi, theta))
    $
  ]
]

#block[
  #align(center)[
    $
      bold(s)_q' = (cos theta sin psi, sin theta, cos theta cos psi)
    $
  ]
]

#block[
  #align(center)[
    $
      #(symb.oracle.center) _q = #T(symb.frame.w, symb.frame.r) (r_q bold(s)_q')
    $
  ]
]

We use standard spherical coordinate relations for the angle/vector conversions
@Formelsammlung-papula2024.

#figure(
  image("/figures/app-paper/pos_ref.png", width: 100%),
  caption: [Candidate centers in the reference frame.],
) <fig:oracle-centers-ref>

=== Candidate orientations (view directions)

For each sampled center $#(symb.oracle.center) _q$, we construct a base camera orientation
according to the configured `ViewDirectionMode`
(#gh("aria_nbv/aria_nbv/pose_generation/orientations.py")). The most common mode
is radial "look-away", which points the camera optical axis away from the
reference rig translation.

#block[
  #align(center)[
    $
      bold(R)_("base") = "look-away"(#(symb.oracle.center) _q, #(symb.ase.traj_final)) \
      #T(symb.frame.w, symb.frame.cq) =
      (bold(R)_("base") compose bold(R)_("delta"), #(symb.oracle.center) _q)
    $
  ]
]

The $(psi, theta)$ caps are applied to the *jitter delta* (box-uniform), not the
base view. See the next subsection for the definition of $bold(R)_("delta")$.

*Radial look-away.* Let $bold(u)_("wup")$ be the world up vector and
$bold(t)_("ref")$ the reference translation (from #(symb.ase.traj_final)).
Define the forward axis

#block[
  #align(center)[
    $
      bold(z)_q =
      ( #(symb.oracle.center) _q - bold(t)_("ref") ) / (|| #(symb.oracle.center) _q - bold(t)_("ref") ||_2 + epsilon)
    $
  ]
]

and construct a roll-stable orthonormal basis

#block[
  #align(center)[
    $
      bold(y)_q =
      ( bold(u)_("wup") - (bold(u)_("wup") dot bold(z)_q) bold(z)_q )
      / (|| bold(u)_("wup") - (bold(u)_("wup") dot bold(z)_q) bold(z)_q ||_2 + epsilon),
      quad
      bold(x)_q = bold(y)_q times bold(z)_q
    $
  ]
]

The resulting rotation is $bold(R)_("base") = [bold(x)_q, bold(y)_q, bold(z)_q]$,
which avoids pathological roll behavior for near-vertical directions.

#figure(
  image("/figures/app-paper/view_dirs_ref.png", width: 100%),
  caption: [View direction density (azimuth/elevation).],
) <fig:oracle-view-dirs-ref>

=== Candidate orientations (view jitter)

After base pose construction, we optionally apply bounded yaw/pitch/roll
perturbations. Box-uniform caps apply to yaw/pitch, with optional roll:

#block[
  #align(center)[
    $
      psi ~ cal(U)(-psi_delta / 2, psi_delta / 2) \
      theta ~ cal(U)(-theta_delta / 2, theta_delta / 2) \
      phi ~ cal(U)(-phi_delta, phi_delta)
    $
  ]
]

#block[
  #align(center)[
    $
      // NOTE: fixed, keep white space after _<...>
      bold(R)_("delta") = bold(R)_z (psi) bold(R)_y (theta) bold(R)_x (phi) \
      #T(symb.frame.w, symb.frame.cq) =
      #T(symb.frame.w, symb.frame.cq) compose mat(bold(R)_("delta"), bold(0); bold(0)^T, 1)
    $
  ]
]

#figure(
  image("/figures/app-paper/orientation_jitter.png", width: 100%),
  caption: [Orientation jitter distribution (delta yaw/pitch/roll, deg).],
) <fig:oracle-orientation-jitter>

#figure(
  image("/figures/app-paper/ypr_reference.png", width: 100%),
  caption: [Reference-frame yaw/pitch/roll distribution after look-away + jitter (deg).],
) <fig:oracle-ypr-reference>

@fig:oracle-orientation-jitter verifies that the sampled view jitter stays
within the configured caps. @fig:oracle-ypr-reference shows the resulting yaw,
pitch, and roll distribution in the reference frame after composing `look-away`
with the jitter rotation.

=== Candidate pruning rules

Candidates are oversampled and then filtered by modular rule objects
(#gh("aria_nbv/aria_nbv/pose_generation/candidate_generation_rules.py")). Let
#symb.ase.mesh be the GT mesh and $cal(B)$ be the snippet occupancy AABB.

#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Candidate pruning configuration (effective).],
  [
    #publication-table(
      columns: (14em, auto),
      header: ([Parameter], [Value]),
      align: (left, left),
      rows: (
      [min_distance_to_mesh],
      [#gen_cfg.min_distance_to_mesh m], [ensure_collision_free],
      [#gen_cfg.ensure_collision_free], [collision_backend],
      [#gen_cfg.collision_backend], [ray_subsample],
      [#gen_cfg.ray_subsample], [step_clearance],
      [#gen_cfg.step_clearance m], [ensure_free_space],
      [#gen_cfg.ensure_free_space],
      ),
    )
  ],
) <tab:oracle-cfg-prune>

*Mesh clearance.* Reject candidates too close to the mesh:

#block[
  #align(center)[
    $
      d_i = min_(bold(m) in #symb.ase.mesh) || #(symb.oracle.center) _i - bold(m) ||_2,
      quad
      d_i > d_"min"
    $
  ]
]

*Path collision.* Reject candidates whose straight segment from the reference to
the candidate center intersects the mesh. In the discretized variant, we sample
points along the segment and require a minimum clearance:

#block[
  #align(center)[
    $
      bold(s)_(i,k) = bold(t)_("ref") + alpha_k (#(symb.oracle.center) _i - bold(t)_("ref")),
      quad alpha_k in [0, 1], \
      min_(bold(m) in #symb.ase.mesh) || bold(s)_(i,k) - bold(m) ||_2 > delta
    $
  ]
]

*Free space.* Reject candidates outside the occupancy bounds:
$(#symb.oracle.center)_i in cal(B)$.

== Candidate depth rendering

For each candidate pose $q$, we render a depth map from the GT mesh using a
metric z-buffer (PyTorch3D rasterizer with `in_ndc=false`). We backproject valid
depth pixels into world coordinates to obtain $#symb.oracle.points_q$. We treat
hits as valid if they correspond to a rasterized face and the resulting depth
lies inside configured bounds ($z_"near" < z < z_"far"$); invalid/missing pixels
are masked out and do not contribute to the fused point cloud. This ensures
that the oracle computation respects the same geometric visibility constraints
as the candidate camera.

Depth rendering is implemented in #gh("aria_nbv/aria_nbv/rendering/pytorch3d_depth_renderer.py") using PyTorch3D's
`PerspectiveCameras`, `RasterizationSettings`, and `MeshRasterizer`
@PyTorch3D-Cameras-2025. We use hard z-buffering with `faces_per_pixel=1` and
`blur_radius=0`, clip triangles closer than `znear`, and expose performance
knobs such as `bin_size` via the renderer config.

#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [Depth rendering configuration (effective).],
  [
    #publication-table(
      columns: (14em, auto),
      header: ([Parameter], [Value]),
      align: (left, left),
      rows: (
      [max_candidates_final],
      [#depth_cfg.max_candidates_final], [resolution_scale],
      [#depth_cfg.resolution_scale], [znear],
      [#renderer_cfg.znear m], [zfar],
      [#renderer_cfg.zfar m], [cull_backfaces],
      [#renderer_cfg.cull_backfaces], [blur_radius],
      [#renderer_cfg.blur_radius], [bin_size],
      [#renderer_cfg.bin_size], [dtype],
      [#renderer_cfg.dtype],
      ),
    )
  ],
) <tab:oracle-cfg-render>

*Pose conventions.* Our poses are stored as world #sym.arrow.l camera transforms.
PyTorch3D expects a world #sym.arrow.r view mapping using row vectors:
$bold(x)_("cam") = bold(x)_("world") bold(R) + bold(T)$.
We therefore invert the pose and transpose the rotation before passing it to
PyTorch3D (see in-code comments in the renderer).

The rasterizer outputs a z-buffer #(symb.oracle.depth_q) and a face-index buffer
`pix_to_face`. Valid pixels satisfy `pix_to_face >= 0` and are further clipped
to `znear < depth < zfar`.

#figure(
  image("/figures/app-paper/cand_renders_1x3.png", width: 100%),
  caption: [Candidate depth renders (1x3).],
) <fig:oracle-depth-renders>

#figure(
  image("/figures/app-paper/depth_histograms_3x3.png", width: 100%),
  caption: [Depth histograms across candidates (3x3).],
) <fig:oracle-depth-histograms>

The depth renders in @fig:oracle-depth-renders are used to sanity-check geometric
conventions (camera poses, handedness, and near/far clipping), while the
histograms in @fig:oracle-depth-histograms reveal depth discontinuities and
spurious spikes that can arise from misconfigured rasterization or invalid
triangles.

== Backprojection and NDC alignment

We convert each depth image to a point cloud via
`backproject_depths_p3d_batch` in
#gh("aria_nbv/aria_nbv/rendering/unproject.py"). For pixel centers
$(u + 1/2, v + 1/2)$ we first map to PyTorch3D's *normalized device coordinates*
(NDC) using the convention (+X left, +Y up) and the scale
$s = min(#symb.shape.H, #symb.shape.Wdim)$ @PyTorch3D-Cameras-2025:

#block[
  #align(center)[
    $
      x_"ndc" = - (u + 1/2 - #symb.shape.Wdim'/2) (2/s), \
      y_"ndc" = - (v + 1/2 - #symb.shape.H'/2) (2/s)
    $
  ]
]

We then unproject in NDC space:

#block[
  #align(center)[
    $
      bold(p)_"world" =
      Pi^(-1)(x_"ndc", y_"ndc", d_q, #symb.oracle.cameras_q),
      quad d_q = #(symb.oracle.depth_q) (u,v)
    $
  ]
]

*Why NDC?* With `PerspectiveCameras(in_ndc=false)` and non-square images,
PyTorch3D internally uses an NDC-like normalization tied to
$min(#symb.shape.H, #symb.shape.Wdim)$.
Backprojecting from pixel coordinates (`from_ndc=false`) yields points in a
different screen convention than the rasterizer, which empirically leads to
backprojected points that do not lie on the rendered mesh. Converting pixels to
the same NDC convention used by the rasterizer makes depth unprojection and
rasterization consistent.

The per-candidate point set is then
$(#(symb.oracle.points_q) _i = { bold(p)_("world") : (u,v) "valid" })$, optionally
subsampled by a stride to control point count.

// Qualitative check: backprojection should align with the GT mesh and the
// semi-dense point cloud (geometry + frame conventions).
#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/app-paper/backproj+semi.png", width: 100%),
    image("/figures/app-paper/semi-dense-pc-cand-vis.png", width: 100%),
  ),
  caption: [Oracle fusion diagnostics: backprojected candidate points align with the GT mesh (left) and candidate visibility over the semi-dense reconstruction (right).],
) <fig:oracle-fusion-diagnostics>

== Oracle RRI computation

We measure reconstruction quality using a Chamfer-style point #sym.arrow.l.r
mesh distance between a point set #symb.oracle.points and a mesh surface
#symb.ase.mesh (triangles #symb.ase.faces). We evaluate both directional terms
using squared point-to-triangle and triangle-to-point distances:

#block[#align(center)[#eqs.rri.cd]]
#block[#align(center)[#eqs.rri.acc]]
#block[#align(center)[#eqs.rri.comp]]

For each candidate, we fuse the semi-dense reconstruction with the candidate
point cloud:

#block[#align(center)[#eqs.rri.union]]

The Relative Reconstruction Improvement for candidate $bold(q)$ is then

#block[#align(center)[#eqs.rri.rri]]

Here $epsilon$ is a small stabilizer. A positive RRI means that adding the
candidate view decreases the Chamfer distance, thereby improving reconstruction
quality.

In practice, candidate scoring is batched on GPU: the ground-truth mesh is
cropped to an occupancy-aligned bounding box shared across candidates and the
point↔mesh distances are evaluated for all candidates in a single forward pass
whenever memory permits. A crop that contains no mesh faces is treated as an
invalid oracle input rather than falling back to full-scene scoring.

Conceptually, the *accuracy* term #symb.oracle.acc measures how well the point
set #symb.oracle.points lies on the GT surface: it averages the squared
distance from each point $bold(p) in #symb.oracle.points$ to its nearest mesh
triangle $bold(f) in #symb.ase.faces$. Thus, #symb.oracle.acc penalizes noisy
or misregistered points that do not agree with the mesh.

The *completeness* term #symb.oracle.comp measures how much of the GT surface
is *covered* by the points: it averages the squared distance from each triangle
$bold(f) in #symb.ase.faces$ to its nearest point $bold(p) in #symb.oracle.points$.
Thus, #symb.oracle.comp penalizes missing surface coverage (holes / unobserved
regions).

We report the Chamfer-style distance as the sum
$"CD"(#symb.oracle.points, #symb.ase.mesh) = #symb.oracle.acc + #symb.oracle.comp$
and use an $epsilon$ stabilizer in the RRI denominator.

// #figure(
//   grid(
//     columns: (1fr, 1fr),
//     gutter: 10pt,
//     image("/figures/app-paper/acc_top10.png", width: 100%), image("/figures/app-paper/comp_top10.png", width: 100%),
//   ),
//   caption: [Top candidates by accuracy (left) and completeness (right) improvements.],
// )

#figure(
  image("/figures/app-paper/oracle_rri_bar.png", width: 100%),
  caption: [Oracle RRI values across candidates for a representative snippet (skewed distribution).],
)

// <rm>
// Devlog-style commentary (and typo “reaveals”). Prefer a single neutral sentence or remove.
Inspecting this single-snippet candidate RRI bar plot reaveals a highly skewed distribution with many extremely small values and a few strong candidates. This motivates our choice of quantile-based binning for CORAL (next section).
// </rm>


== Ordinal binning for CORAL (label post-processing)

To train with CORAL, we discretize continuous RRIs into $K$ ordered bins using
empirical quantile edges (#gh("aria_nbv/aria_nbv/rri_metrics/ordinal.py")).
Given a stream of oracle RRIs $\{r_n\}_{n=1}^N$, we compute $K-1$ edges at the
quantiles $k/K$:

#block[#align(center)[#eqs.binning.edges]]

The ordinal label is then the number of edges below the value (implemented via
#link("https://docs.pytorch.org/docs/stable/generated/torch.bucketize.html")[`torch.bucketize`]):

#block[#align(center)[#eqs.binning.label]]

CORAL represents the label $y$ as binary level targets @CORAL-cao2019:

#block[#align(center)[#eqs.binning.levels]]


#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/coral/rri_distribution_linear.png", width: 100%),
    image("/figures/coral/rri_distribution_log_with_bin_edges.png", width: 100%),

    image("/figures/coral/ordinal_label_histogram_fit.png", width: 100%),
  ),
  caption: [Oracle RRI distribution and fitted quantile binning (fit data). The skewed distribution motivates discretization; quantile edges yield approximately uniform ordinal class counts.],
) <fig:coral-binning-overview>

#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/coral/bin_means_vs_midpoints.png", width: 100%),
    image("/figures/coral/bin_stds_vs_uniform_baseline.png", width: 100%),
  ),
  caption: [Per-bin statistics for ordinal bins (fit data). Quantile bins have uneven widths; we initialize bin representatives from bin means and monitor calibration and variance across bins.],
) <fig:coral-binning-stats>
