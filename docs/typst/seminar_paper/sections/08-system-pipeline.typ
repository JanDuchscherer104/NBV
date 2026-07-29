#import "@preview/booktabs:0.0.4": *
#show: booktabs-default-table-style

#import "../../shared/macros.typ": *
#let labeler_cfg = toml("/typst/shared/data/paper_figures_oracle_labeler.toml")
#let gen_cfg = labeler_cfg.labeler.generator
#let depth_cfg = labeler_cfg.labeler.depth
#let renderer_cfg = depth_cfg.renderer

= System Pipeline and Implementation

Our pipeline follows a modular
path from data ingestion to oracle label computation (and future candidate
scoring). The key stages are
summarized in @tab:pipeline and visualized in @fig:candidate-poses.


#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/app-paper/pos_ref.png", width: 100%),
    image("/figures/app-paper/view_dirs_ref.png", width: 100%),
    image("/figures/app-paper/orientation_jitter.png", width: 100%),
  ),
  caption: [Candidate sampling diagnostics: candidate centers (reference frame), view-direction density, and orientation jitter.],
) <fig:candidate-poses>

#figure(
  kind: "table",
  supplement: [Table],
  caption: [Pipeline modules and data flow.],
  table(
    columns: (14em, auto, auto),
    align: (left, left, left),
    toprule(),
    table.header([Module], [Inputs], [Outputs]),
    midrule(),
    [Dataset loader],
    [ASE shards, mesh],
    [Snippet window (streams, poses, semi-dense points, mesh)],
    [Candidate generation],
    [Rig pose, mesh, bounds],
    [Candidate poses],
    [Depth rendering],
    [Candidates, mesh, cameras],
    [Depth maps, masks],
    [Oracle RRI],
    [$#(symb.oracle.points) _t, #symb.oracle.points_q, #symb.ase.mesh$],
    [RRI labels (continuous + ordinal)],
    [Future: learned scorer],
    [oracle labels, scene features],
    [Predicted ordinal scores],
    bottomrule(),
  ),
) <tab:pipeline>

#figure(
  kind: "table",
  supplement: [Table],
  caption: [Oracle label configuration used when building the VIN offline store.],
  table(
    columns: (18em, auto),
    align: (left, left),
    toprule(),
    table.header([Parameter], [Value]),
    midrule(), [Candidate count (requested)],
    [#gen_cfg.num_samples], [Candidate shell radius],
    [[#gen_cfg.min_radius, #gen_cfg.max_radius] m], [Elevation range],
    [#gen_cfg.min_elev_deg#sym.degree to #gen_cfg.max_elev_deg#sym.degree], [Azimuth spread],
    [#gen_cfg.delta_azimuth_deg#sym.degree], [Direction sampler],
    [#gen_cfg.sampling_strategy ($kappa = #gen_cfg.kappa$)], [Oversample factor / resamples],
    [#gen_cfg.oversample_factor / #gen_cfg.max_resamples], [Min distance to mesh],
    [$#gen_cfg.min_distance_to_mesh$ m], [Collision + free-space checks],
    [enabled (#gen_cfg.collision_backend)], [View direction mode],
    [#gen_cfg.view_direction_mode], [View jitter caps],
    [#gen_cfg.view_max_azimuth_deg#sym.degree az / #gen_cfg.view_max_elevation_deg#sym.degree elev], [View roll jitter],
    [#gen_cfg.view_roll_jitter_deg#sym.degree], [Ray subsample / step clearance],
    [#gen_cfg.ray_subsample / #gen_cfg.step_clearance m], [Depth renderer (max kept)],
    [#depth_cfg.max_candidates_final], [Depth z-range],
    [znear=#renderer_cfg.znear, zfar=#renderer_cfg.zfar], [Backprojection stride],
    [#labeler_cfg.labeler.backprojection_stride], [Oracle reduction],
    [mean over triangles (cropped AABB)], bottomrule(),
  ),
) <tab:oracle-label-config>

The corresponding runtime configuration is stored in
`.configs/inspection/figures/paper_figures_oracle_labeler.toml`.

== Candidate generation

Candidates are sampled on a constrained spherical shell around the current rig
pose, with configurable radius and elevation limits. We enforce collision
constraints using free-space and mesh intersection checks. The candidate set is
kept discrete to enable reproducible oracle label computation and to match the
candidate-ranking formulation of VIN-NBV @VIN-NBV-frahm2025.

Candidate sampling diagnostics are shown in @fig:candidate-poses; Streamlit
snippet context is shown in @fig:streamlit-diagnostics.

== Rendering and backprojection

We render candidate depth maps with PyTorch3D and backproject depths to world
points by converting pixel centers to PyTorch3D NDC coordinates (to match the
rasterizer) before unprojection. These points are fused with the
semi-dense SLAM reconstruction to form the candidate-augmented point cloud. The
rendering step is expensive but performed offline to generate oracle labels.

We explicitly track valid depth pixels with a per-pixel validity mask, ensuring
that missing pixels or z-buffer failures do not pollute the candidate point cloud.
This mask is also useful for debugging candidate views that appear to look
through walls or miss the mesh entirely.

== Streamlit diagnostics

A Streamlit dashboard exposes the pipeline stages with cached intermediate
results. We inspect candidate distributions, depth render quality, and oracle
RRI behavior to identify failure modes and verify coordinate conventions.

// NOTE: Formerly part of a slide-figure gallery appendix (removed); keep it
// close to the pipeline implementation section where the dashboard is introduced.
#figure(
  grid(
    columns: (1fr, 1fr),
    gutter: 10pt,
    image("/figures/app/traj.png", width: 100%),
    image("/figures/app/semidense.png", width: 100%),
  ),
  caption: [Streamlit snippet diagnostics: trajectory and semi-dense overlay.],
) <fig:streamlit-diagnostics>
