# Official Rerun Example Routes

Use this file to choose an upstream comparison, not to copy an API contract.
Pages and examples can change; confirm the page is current and then verify the
installed SDK plus ARIA call sites and tests.

- [Examples index](https://rerun.io/examples) — search current examples by
  archetype or task before relying on recollection.
- [RGBD](https://rerun.io/examples/robotics/rgbd) — choose for paired pinhole,
  RGB, metric depth, entity hierarchy, and timelines.
- [Live depth sensor](https://rerun.io/examples/robotics/live_depth_sensor) —
  choose for `Transform3D`, calibrated pinholes, streaming RGB/depth, and metric
  depth units.
- [SDK operating modes](https://rerun.io/docs/reference/sdk-operating-modes) —
  choose for `save`, `spawn`, `connect_grpc`, servers, or multiple sinks.
- [DepthImage archetype](https://rerun.io/docs/reference/types/archetypes/depth_image)
  — choose for depth scaling and camera-backed 3D interpretation.
- [Boxes3D archetype](https://rerun.io/docs/reference/types/archetypes/boxes3d)
  — choose for batched oriented boxes, labels, colours, and radii.
- [Eye control](https://rerun.io/examples/feature-showcase/eye_control) — choose
  only for blueprint-driven viewer camera or presentation behavior.
- [Stable Python API](https://ref.rerun.io/docs/python/stable/common/) — use for
  the current public Python signatures after selecting an example.

Do not make example entity paths, defaults, versions, or viewer layouts into
ARIA invariants. The repository package README, code, configuration, and tests
remain authoritative.
