#import "@preview/cetz:0.5.2"

#set page(width: 160mm, height: 72mm, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.5pt, fill: rgb("#17202a"))

#let ink = rgb("#17202a")
#let muted = rgb("#687380")
#let hair = rgb("#cbd3dc")
#let forward = rgb("#31689e")
#let target = rgb("#c17d11")
#let bypass = rgb("#18836d")
#let target-object = rgb("#a94f2a")

#let polar(origin, angle, radius) = (
  origin.at(0) + radius * calc.sin(angle),
  origin.at(1) + radius * calc.cos(angle),
)

#let unit2(angle) = (calc.sin(angle), calc.cos(angle))
#let dot2(a, b) = a.at(0) * b.at(0) + a.at(1) * b.at(1)
#let add2(a, b) = (a.at(0) + b.at(0), a.at(1) + b.at(1))
#let sub2(a, b) = (a.at(0) - b.at(0), a.at(1) - b.at(1))
#let scale2(a, scale-factor) = (a.at(0) * scale-factor, a.at(1) * scale-factor)
#let normalize2(a) = {
  let norm = calc.sqrt(dot2(a, a))
  (a.at(0) / norm, a.at(1) / norm)
}
#let angle2(a) = calc.atan2(a.at(0), a.at(1))
#let look-angle(point, destination) = calc.atan2(
  destination.at(0) - point.at(0),
  destination.at(1) - point.at(1),
)

#let transformed-angle(raw-angle, base-angle, spread) = {
  let raw = unit2(raw-angle)
  let base = unit2(base-angle)
  let orthogonal = sub2(raw, scale2(base, dot2(raw, base)))
  angle2(normalize2(add2(base, scale2(orthogonal, spread))))
}

#let bypass-angle(raw-angle, bearing-angle) = {
  let raw = unit2(raw-angle)
  let bearing = unit2(bearing-angle)
  let lateral = unit2(bearing-angle + 90deg)
  let signed-lateral = scale2(lateral, if raw.at(0) >= 0 { 1 } else { -1 })
  // The plan view omits the bounded vertical term retained by the adjacent
  // canonical equation.
  angle2(normalize2(add2(scale2(bearing, .55), scale2(signed-lateral, .85))))
}

#let frame(origin) = {
  import cetz.draw: *
  let z-tip = polar(origin, 0deg, .58)
  let x-tip = polar(origin, 90deg, .45)
  circle(origin, radius: .063, fill: ink, stroke: none)
  line(origin, z-tip, stroke: 1pt + ink, mark: (end: ">", scale: .60))
  line(origin, x-tip, stroke: .78pt + muted, mark: (end: ">", scale: .54))
  content(z-tip, anchor: "south", text(size: 7.4pt)[$z$])
  content(x-tip, anchor: "west", text(size: 7.4pt, fill: muted)[$x$])
  content((origin.at(0), origin.at(1) - .22), anchor: "north", text(size: 7.8pt, weight: "bold")[$bold(T)_r^w$])
}

#let target-glyph(point) = {
  import cetz.draw: *
  circle(point, radius: .15, fill: target-object.transparentize(72%), stroke: 1.05pt + target-object)
  line((point.at(0) - .21, point.at(1)), (point.at(0) + .21, point.at(1)), stroke: .6pt + target-object)
  line((point.at(0), point.at(1) - .21), (point.at(0), point.at(1) + .21), stroke: .6pt + target-object)
}

#let family-marker(point, color, shape) = {
  import cetz.draw: *
  let radius = .096
  if shape == "circle" {
    circle(point, radius: radius, fill: color, stroke: .72pt + color)
  } else if shape == "diamond" {
    line(
      (point.at(0), point.at(1) + radius * 1.2),
      (point.at(0) + radius, point.at(1)),
      (point.at(0), point.at(1) - radius * 1.2),
      (point.at(0) - radius, point.at(1)),
      close: true,
      fill: color,
      stroke: .72pt + color,
    )
  } else {
    line(
      (point.at(0), point.at(1) + radius * 1.3),
      (point.at(0) + radius * 1.15, point.at(1) - radius),
      (point.at(0) - radius * 1.15, point.at(1) - radius),
      close: true,
      fill: color,
      stroke: .72pt + color,
    )
  }
}

#let construction(origin, family, color, mode, raw-angle) = {
  import cetz.draw: *
  let bearing-angle = 48deg
  let target-point = polar(origin, bearing-angle, 3.48)
  let result-angle = if mode == "forward" {
    transformed-angle(raw-angle, 0deg, .45)
  } else if mode == "target" {
    transformed-angle(raw-angle, bearing-angle, .40)
  } else {
    bypass-angle(raw-angle, bearing-angle)
  }

  content(
    (origin.at(0) - .48, 6.88),
    anchor: "north-west",
    box(
      width: 42mm,
      text(
        size: if mode == "bypass" { 8.3pt } else { 9pt },
        weight: "bold",
        fill: color,
        family,
      ),
    ),
  )

  frame(origin)
  if mode != "forward" {
    line(origin, target-point, stroke: (paint: muted, thickness: .68pt, dash: "dashed"))
    target-glyph(target-point)
    content((target-point.at(0) + .15, target-point.at(1) + .10), anchor: "south-west", text(size: 7.5pt, fill: target-object)[$bold(p)_e$])
  }

  let raw-tip = polar(origin, raw-angle, 1.72)
  line(origin, raw-tip, stroke: (paint: muted, thickness: .78pt, dash: "dotted"), mark: (end: ">", scale: .54))
  content(raw-tip, anchor: if raw-angle < 0deg { "east" } else { "west" }, text(size: 7.4pt, fill: muted)[$bold(d)_i^0$])

  let centre = polar(origin, result-angle, 2.12)
  line(origin, centre, stroke: 1.18pt + color, mark: (end: ">", scale: .58))
  family-marker(
    centre,
    color,
    if mode == "forward" { "circle" } else if mode == "target" { "diamond" } else { "triangle" },
  )
  content((centre.at(0), centre.at(1) - .19), anchor: "north", text(size: 7.4pt, fill: color)[$bold(c)_i$])

  let base-gaze = if mode == "forward" { 0deg } else { look-angle(centre, target-point) }
  let realized-gaze = base-gaze + if mode == "bypass" { -8deg } else { 7deg }
  line(centre, polar(centre, base-gaze, .88), stroke: (paint: ink, thickness: .76pt, dash: "dashed"), mark: (end: ">", scale: .50))
  line(centre, polar(centre, realized-gaze, .88), stroke: 1pt + color, mark: (end: ">", scale: .52))
  arc(centre, start: calc.min(base-gaze, realized-gaze), stop: calc.max(base-gaze, realized-gaze), radius: .36, stroke: .52pt + muted)
}

#cetz.canvas(length: 9.48mm, padding: .08, {
  import cetz.draw: *

  construction((1.06, 3.08), [forward-local], forward, "forward", 31deg)
  construction((6.59, 3.08), [target-bearing-local], target, "target", 31deg)
  construction((12.12, 3.08), [lateral-target-bypass], bypass, "bypass", 31deg)

  line((5.32, 1.48), (5.32, 7.12), stroke: .45pt + hair)
  line((10.85, 1.48), (10.85, 7.12), stroke: .45pt + hair)

  line((.42, 1.25), (16.36, 1.25), stroke: .48pt + hair)
  line((.70, .70), (1.34, .70), stroke: (paint: muted, thickness: .76pt, dash: "dotted"), mark: (end: ">", scale: .50))
  content((1.49, .70), anchor: "west", text(size: 7.2pt)[raw draw])
  line((4.18, .70), (4.82, .70), stroke: 1.08pt + ink, mark: (end: ">", scale: .52))
  content((4.97, .70), anchor: "west", text(size: 7.2pt)[transformed centre])
  line((8.44, .70), (9.08, .70), stroke: (paint: ink, thickness: .76pt, dash: "dashed"), mark: (end: ">", scale: .50))
  content((9.23, .70), anchor: "west", text(size: 7.2pt)[base gaze])
  line((12.04, .70), (12.68, .70), stroke: 1pt + ink, mark: (end: ">", scale: .52))
  content((12.83, .70), anchor: "west", text(size: 7.2pt)[jittered gaze])
})
