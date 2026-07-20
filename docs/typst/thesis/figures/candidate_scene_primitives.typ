#import "@preview/cetz:0.5.2": draw

// Publication wire primitives for projected 3D overlays.
// The frustum topology is generated from Viser's five-vertex wire convention
// (Apache-2.0) in scripts/export_candidate_scene_geometry.py. This Typst layer
// only joins already projected endpoints; it never invents screen geometry.

#let panel-point(point, width, height) = (
  point.at(0) * width,
  point.at(1) * height,
)

#let wire-segments(segments, width, height, stroke) = {
  for segment in segments {
    draw.line(
      ..segment.map(point => panel-point(point, width, height)),
      stroke: stroke,
    )
  }
}

#let candidate-marker(point, width, height, valid: true, selected: false, colors: (:)) = {
  let p = panel-point(point, width, height)
  if selected {
    let radius = .075
    draw.line(
      (p.at(0), p.at(1) + radius),
      (p.at(0) + radius, p.at(1)),
      (p.at(0), p.at(1) - radius),
      (p.at(0) - radius, p.at(1)),
      close: true,
      fill: colors.at("selected"),
      stroke: .8pt + colors.at("ink"),
    )
  } else if valid {
    draw.circle(
      p,
      radius: .035,
      fill: colors.at("valid"),
      stroke: .35pt + colors.at("ink"),
    )
  } else {
    let radius = .04
    draw.line(
      (p.at(0) - radius, p.at(1) - radius),
      (p.at(0) + radius, p.at(1) + radius),
      stroke: .65pt + colors.at("invalid"),
    )
    draw.line(
      (p.at(0) - radius, p.at(1) + radius),
      (p.at(0) + radius, p.at(1) - radius),
      stroke: .65pt + colors.at("invalid"),
    )
  }
}
