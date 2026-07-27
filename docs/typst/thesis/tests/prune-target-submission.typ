#import "../draft_markers.typ": prune_target

#prune_target(
  [Submission builds must reject unresolved prune targets.],
  key: "fixture.prune-target",
  reason: "fixture",
  static_occurrences: 0,
  build_occurrences: "not available",
)
