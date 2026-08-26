#pagebreak()

= Appendix: VIN Pose Frames and Consistency Checks <sec:appendix-pose-frames>

#import "../../shared/macros.typ": *
#import "../../shared/tables.typ": publication-table

This appendix summarizes the SE(3) frames provided to `VinModelV3.forward`,
using the notation from the coordinate conventions section.
// <rm>
// Internal dev setup references (debug launcher, VSCode). Remove from paper.
We verify the conventions with offline-cache data loaded via `.configs/offline_only.toml`
(the debug config in `.vscode/launch.json`).
// </rm>
// TODO(paper-cleanup): Keep this appendix as the canonical “CW90 consistency” reference and
// ensure other sections (coordinate conventions / architecture) do not restate it differently.

== CW90 rig-basis correction (`rotate_yaw_cw90`)

`rotate_yaw_cw90` is a fixed 90#sym.degree twist about the pose-local $+z$
(forward) axis (a roll); the name is historical. In the current pipeline,
candidates are generated about #symb.ase.traj_final after applying
`rotate_yaw_cw90` to that reference pose. Without this one-time rig-basis
correction, the candidate sampling azimuth and elevation effectively swap
when interpreted in a right-handed LUF camera frame.

This correction must be applied *at most once* along any path. Plotting code may
apply the same twist purely for display; do not apply it again to already-corrected
poses. If the rotation is undone for learning or diagnostics (e.g.,
`apply_cw90_correction=True`), the same undo must be reflected in the associated
PyTorch3D cameras; otherwise pose encoding and projection features desynchronize
(see checks below).

== Inputs to `forward`

Frame glossary (consistent with the main notation):

- #symb.frame.w: global world frame (gravity-aligned).
- #symb.frame.r: reference rig frame for the snippet (physical headset pose).
- #symb.frame.cq: candidate camera frame in LUF coordinates (left-up-forward).
- #symb.frame.v: EVL voxel grid frame (local, gravity-aware).

#figure(
  kind: "table",
  supplement: [Table],
  placement: none,
  caption: [SE(3) inputs passed into `VinModelV3.forward` and their frame meaning.],
  [
    #publication-table(
      columns: (auto, auto, auto, auto),
      header: ([Input], [Notation], [SE(3) meaning], [Notes]),
      align: (left, center, left, left),
      text-size: 7pt,
      rows: (
      [#code-inline("candidate_poses_") #linebreak() #code-inline("world_cam")],
      [$#T(symb.frame.w, symb.frame.cq)$],
      [world #sym.arrow.r camera (PoseTW)],

      [Pose of each candidate camera in world coordinates.],
      [#code-inline("reference_pose_") #linebreak() #code-inline("world_rig")],
      [$#T(symb.frame.w, symb.frame.r)$],
      [world #sym.arrow.r rig reference (PoseTW)],

      [Physical rig pose; not gravity-aligned in cache.],
      [#code-inline("p3d_cameras")],
      [$#T(symb.frame.cq, symb.frame.w)$],
      [camera #sym.arrow.r world (PerspectiveCameras)],

      [PyTorch3D row-vector convention, with $#T(symb.frame.cq, symb.frame.w) = #T(symb.frame.w, symb.frame.cq)^(-1)$.],
      [#code-inline("backbone_out.") #linebreak() #code-inline("t_world_voxel")],
      [$#T(symb.frame.w, symb.frame.v)$],
      [world #sym.arrow.r voxel (PoseTW)],

      [EVL voxel grid pose for sampling voxel-aligned fields.],
      [#code-inline("backbone_out.") #linebreak() #code-inline("pts_world")],
      [$bold(p)^(#symb.frame.w)$],
      [points in world frame],

      [Voxel-center points used for positional encoding and pooling.]),
    )
  ],
) <tab:vin-input-frames>

*Derived frames inside the model.* The pose encoder builds candidate poses in
the reference rig frame
$#T(symb.frame.r, symb.frame.cq) = #T(symb.frame.w, symb.frame.r)^(-1)#T(symb.frame.w, symb.frame.cq)$.
Semidense and voxel projections are evaluated in camera frames derived from
`p3d_cameras` and must be consistent with the above pose encoding.

== Offline-cache consistency checks

Using cached batches (same config as the debug launcher), we verified:

- `candidate_poses_world_cam` and `p3d_cameras` are consistent:
  $#T(symb.frame.cq, symb.frame.w)$ reconstructed from `candidate_poses_world_cam`
  matches `p3d_cameras` with max abs error $<= 1e-6$.
- Undoing the CW90 display correction on poses *without* rotating
  `p3d_cameras` breaks that alignment (max abs error approx 1.2 in R,
  approx 10 in t), which corrupts semidense projection features.

== Current issues

// <rm>
// Internal issue tracker / implementation notes; move to repo docs or issues.
- #textbf[CW90 correction mismatch]: `apply_cw90_correction=True` in
  `VinModelV3` only adjusts poses unless the caller pre-corrects
  `p3d_cameras`. This can desynchronize pose encoding and projection
  features.
- #textbf[Missing gravity-aligned reference in cache]: offline cache stores only
  `reference_pose_world_rig` (physical rig). The gravity-aligned sampling pose
  is not available, so cached datasets cannot be retrofitted without recompute.
- #textbf[Mixed display vs. physical frames]: display-only rotations (CW90) should
  not leak into model inputs.
// </rm>

== Recommended streamlining

// <rm>
// Internal refactor plan; move to repo docs.
1. #textbf[Single canonical frame per batch]: treat all cached inputs as physical
  rig frames; disable CW90 inside the model for cached datasets.
2. #textbf[Batch-level normalization helper]: if we want to undo CW90, apply it
  consistently to `candidate_poses_world_cam`, `reference_pose_world_rig`,
  and `p3d_cameras` (plus a `cw90_corrected` tag) before entering `forward`.
// </rm>

The CW90 consistency guard is implemented in `VinModelV3.forward`: it raises
if `apply_cw90_correction=True` without a `p3d_cameras.cw90_corrected` tag.
