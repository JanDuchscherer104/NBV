#import "@preview/cetz:0.5.2"

#set page(width: 160mm, height: 72.5mm, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8pt, fill: rgb("#17202a"))

#let data = json("data/candidate_scene_81286_000035.json")
#let ink = rgb("#17202a")
#let muted = rgb("#687380")
#let hair = rgb("#cbd3dc")
#let history-path-color = rgb("#aa3377")
#let history-frustum-color = rgb("#0072b2")
#let target-color = rgb("#a95f12")
#let forward-color = rgb("#31689e")
#let bearing-color = rgb("#c06b12")
#let bypass-color = rgb("#18836d")
#let invalid-color = rgb("#a93e4c")
#let selected-color = rgb("#f2c14e")

// The raster is a fixed crop of the original 1500 x 920 projection. Every
// vector point remains in the original normalized panel coordinates and is
// transformed by the identical crop before drawing.
#let crop = (
  xmin: 245 / 1500,
  xmax: 1255 / 1500,
  ymin: 1 - 750 / 920,
  ymax: 1 - 150 / 920,
)

#let crop-point(point, width, height) = (
  (point.at(0) - crop.xmin) / (crop.xmax - crop.xmin) * width,
  (point.at(1) - crop.ymin) / (crop.ymax - crop.ymin) * height,
)

#let panel-point(point, width, height) = (
  point.at(0) * width,
  point.at(1) * height,
)

#let wire-segments(segment-list, point-map, pen) = {
  import cetz.draw: *
  for segment in segment-list {
    line(..segment.map(point-map), stroke: pen)
  }
}

#let family-color(candidate) = if candidate.at("family") == "forward_local" {
  forward-color
} else if candidate.at("family") == "target_bearing_local" {
  bearing-color
} else {
  bypass-color
}

#let family-marker(candidate, map-point, selected: false, small: false) = {
  import cetz.draw: *
  let p = map-point(candidate.at("center"))
  let color = family-color(candidate)
  let radius = if small { .025 } else { .055 }
  let fill-color = if selected { selected-color } else { color }
  let border = if selected { .70pt + ink } else { .40pt + white }

  if candidate.at("family") == "forward_local" {
    circle(p, radius: radius, fill: fill-color, stroke: border)
  } else if candidate.at("family") == "target_bearing_local" {
    line(
      (p.at(0), p.at(1) + radius),
      (p.at(0) + radius, p.at(1)),
      (p.at(0), p.at(1) - radius),
      (p.at(0) - radius, p.at(1)),
      close: true,
      fill: fill-color,
      stroke: border,
    )
  } else {
    line(
      (p.at(0), p.at(1) + radius),
      (p.at(0) + radius, p.at(1) - radius),
      (p.at(0) - radius, p.at(1) - radius),
      close: true,
      fill: fill-color,
      stroke: border,
    )
  }
}

#let oblique-view(panel) = {
  let width = 10.8
  let height = 6.42
  let map-point = point => crop-point(point, width, height)

  cetz.canvas(length: 10mm, padding: 0, {
    import cetz.draw: *

    // The processed GT mesh is neutral context; overlays own the explanation.
    content(
      (0, 0),
      (width, height),
      image(
        "data/" + panel.at("background"),
        width: 100%,
        height: 100%,
        fit: "stretch",
      ),
    )

    // The selected task GT OBB has its own accent, independent of history.
    wire-segments(panel.at("target_obb_segments"), map-point, 1.85pt + target-color)
    wire-segments(panel.at("target_obb_segments"), map-point, .42pt + white)

    // Separate the logged path from its sparse historical camera footprints.
    // Both remain distinct from the neutral mesh and the sampling root.
    line(
      ..panel.at("history_path").map(map-point),
      stroke: 2.20pt + white.transparentize(12%),
    )
    line(
      ..panel.at("history_path").map(map-point),
      stroke: 1.24pt + history-path-color,
      mark: (end: ">", scale: .52),
    )
    for pose in panel.at("history_frusta") {
      wire-segments(
        pose,
        map-point,
        (paint: white.transparentize(10%), thickness: 1.72pt, dash: "dashed"),
      )
      wire-segments(
        pose,
        map-point,
        (paint: history-frustum-color, thickness: 1.02pt, dash: "dashed"),
      )
    }
    for row in panel.at("history_rows") {
      circle(
        map-point(panel.at("history_path").at(row)),
        radius: .038,
        fill: white,
        stroke: .88pt + history-frustum-color,
      )
    }
    // Expand only the selected hypothetical view. The full shell remains in B.
    line(
      ..panel.at("selected_path").map(map-point),
      stroke: 2.10pt + selected-color,
    )
    line(
      ..panel.at("selected_path").map(map-point),
      stroke: .58pt + ink,
      mark: (end: ">", scale: .65),
    )
    wire-segments(panel.at("selected_frustum"), map-point, 1.98pt + white.transparentize(8%))
    wire-segments(panel.at("selected_frustum"), map-point, 1.40pt + ink)
    family-marker(panel.at("candidates").at(47), map-point, selected: true)

    // The canonical sampling root is an anchor, not a physical RGB frustum.
    let root = map-point(panel.at("root_center"))
    let physical-rgb-end = map-point(panel.at("history_path").last())
    circle(root, radius: .042, fill: ink, stroke: .40pt + white)
    circle(
      physical-rgb-end,
      radius: .075,
      fill: none,
      stroke: .82pt + history-path-color,
    )
    content(
      (root.at(0) + .18, root.at(1) - .16),
      anchor: "north-west",
      box(
        inset: 1pt,
        fill: white.transparentize(10%),
        text(size: 7pt, weight: "bold")[$r_t$],
      ),
    )

    content(
      (.14, height - .12),
      anchor: "north-west",
      box(
        inset: 1.1pt,
        fill: white.transparentize(8%),
        text(size: 7.3pt, weight: "bold")[A  Scene-grounded selection],
      ),
    )
  })
}

#let audit-view(panel) = {
  let width = 4.8
  let height = 2.95
  let map-point = point => panel-point(point, width, height)

  cetz.canvas(length: 10mm, padding: .01, {
    import cetz.draw: *
    content(
      (0, 0),
      (width, height),
      image(
        "data/" + panel.at("background"),
        width: 100%,
        height: 100%,
        fit: "stretch",
      ),
    )
    wire-segments(panel.at("target_obb_segments"), map-point, 1.25pt + target-color)
    wire-segments(panel.at("target_obb_segments"), map-point, .30pt + white)

    for candidate in panel.at("candidates") {
      let p = map-point(candidate.at("center"))
      if candidate.at("selected") {
        family-marker(candidate, map-point, selected: true, small: true)
      } else if candidate.at("valid") {
        family-marker(candidate, map-point, small: true)
      } else {
        line(
          (p.at(0) - .021, p.at(1) - .021),
          (p.at(0) + .021, p.at(1) + .021),
          stroke: .40pt + invalid-color,
        )
        line(
          (p.at(0) - .021, p.at(1) + .021),
          (p.at(0) + .021, p.at(1) - .021),
          stroke: .40pt + invalid-color,
        )
      }
    }

    line(
      ..panel.at("selected_path").map(map-point),
      stroke: 1.05pt + selected-color,
    )
    line(
      ..panel.at("selected_path").map(map-point),
      stroke: .38pt + ink,
      mark: (end: ">", scale: .55),
    )
    let root = map-point(panel.at("root_center"))
    circle(root, radius: .032, fill: ink, stroke: .30pt + white)
    rect((0, 0), (width, height), fill: none, stroke: .45pt + hair)

    line(..panel.at("scale_bar").map(map-point), stroke: .90pt + ink)
    let scale-start = map-point(panel.at("scale_bar").at(0))
    content(
      (scale-start.at(0) + .28, scale-start.at(1) + .04),
      anchor: "south",
      text(size: 6.2pt)[1 m],
    )
  })
}

#let counts = data.at("counts")

#grid(
  columns: (108mm, 1fr),
  gutter: 3mm,
  oblique-view(data.at("oblique")),
  [
    #text(size: 7.4pt, weight: "bold")[B  Complete-shell geometry audit]
    #v(.4mm)
    #audit-view(data.at("top"))
    #v(.8mm)
    #text(size: 6.9pt, fill: muted)[
      #counts.at("candidates") proposed · #counts.at("valid") admitted ·
      #counts.at("invalid_clearance") rejected
    ]
    #v(.9mm)
    #text(size: 6.3pt, fill: muted)[Configured row blocks:]
    #v(.3mm)
    #grid(
      columns: (auto, 1fr),
      column-gutter: 1.0mm,
      row-gutter: .35mm,
      text(size: 7.5pt, fill: forward-color)[●], text(size: 6.6pt)[forward-local (0--23)],
      text(size: 7.5pt, fill: bearing-color)[◆], text(size: 6.6pt)[target-bearing (24--47)],
      text(size: 7.5pt, fill: bypass-color)[▲], text(size: 6.6pt)[lateral-bypass (48--59)],
      text(size: 7.5pt, fill: invalid-color)[×], text(size: 6.6pt)[hard-rejected],
    )
    #v(.7mm)
    #grid(
      columns: (auto, 1fr),
      column-gutter: 1.0mm,
      row-gutter: .28mm,
      text(size: 7.5pt, fill: ink)[━], text(size: 6.6pt)[selected candidate + route],
      text(size: 7.5pt, fill: history-path-color)[━▶], text(size: 6.6pt)[observed RGB trajectory],
      text(size: 7.5pt, fill: history-frustum-color)[┄], text(size: 6.6pt)[logged RGB camera frusta],
      text(size: 7.5pt, fill: target-color)[▣], text(size: 6.6pt)[task GT OBB],
    )
  ],
)
