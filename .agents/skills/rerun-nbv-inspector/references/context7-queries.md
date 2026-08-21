# Rerun Current-Docs Queries

These are query templates, not API authority. Select the current Rerun library
through [`aria-nbv-context`](../../aria-nbv-context/SKILL.md) and its
[Context7 registry](../../aria-nbv-context/references/context7_library_ids.md);
otherwise open the equivalent official Rerun documentation. Request only the
slice needed for the touched call and verify the installed Python signature
locally.

## Recording and sinks

- `Python recording initialization save spawn connect_grpc sink ordering`
- `Python RecordingStream stable recording_id save rrd flush disconnect`
- `Python multiple sinks set_sinks file and grpc current API`

Use for `_session.py`, CLI output modes, lifecycle ordering, or `.rrd` creation.

## Cameras, transforms, and coordinates

- `Python Transform3D parent child relation translation quaternion matrix`
- `Python Pinhole resolution focal_length principal_point camera_xyz`
- `Python ViewCoordinates right hand Z up static logging`

Use for `_geometry.py`, camera entities, frusta, pose direction, or coordinate
basis work. Local `PoseTW` and `CameraTW` source/tests still own ARIA semantics.

## RGB and metric depth

- `Python Pinhole Image DepthImage same camera entity meter backprojection`
- `Python DepthImage meter datatype invalid pixels colormap 3D interpretation`

Use when depth should be spatially interpreted rather than shown only as a 2D
diagnostic. Verify width/height ordering and local display rotations in code and
tests.

## Entities, timelines, and blueprints

- `Python entity path hierarchy static temporal logging set_time sequence`
- `Python blueprint Spatial3DView TimeSeriesView contents overrides current API`
- `Python batch Points3D LineStrips3D Boxes3D labels colors radii`

Use for entity-tree, timeline, viewer-layout, or repeated-geometry changes.
Blueprints remain presentation policy; local masks and scientific meaning stay
with package owners.
