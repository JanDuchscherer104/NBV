#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let support-color = rgb("#2563eb")
#let obstacle-color = rgb("#991b1b")
#let target-color = rgb("#b45309")
#let valid-color = rgb("#16a34a")
#let invalid-color = rgb("#dc2626")
#let weak-color = rgb("#b45309")
#let root-color = rgb("#334155")

#let tiny(body) = text(size: 5.7pt, fill: muted, body)
#let status-text(body) = text(size: 5.9pt, fill: ink, body)

#cetz.canvas(length: 8mm, padding: .24, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .62)

  let panel(x, y, title, status, tint) = {
    rect((x, y), (x + 4.35, y + 3.95),
      radius: .12,
      fill: panel-fill,
      stroke: .62pt + panel-stroke)
    content((x + 2.18, y + 3.66), align(center, text(size: 6.7pt, weight: "bold", title)))
    rect((x + .25, y + .22), (x + 4.1, y + .82),
      radius: .08,
      fill: tint.lighten(84%),
      stroke: .58pt + tint)
    content((x + 2.18, y + .52), align(center, status-text(status)))
  }

  let support(x, y) = {
    rect((x + .55, y + 1.05), (x + 3.75, y + 3.2),
      radius: .11,
      fill: support-color.lighten(92%),
      stroke: (paint: support-color, thickness: .52pt, dash: "dashed"))
    content((x + .72, y + 3.04), align(left, tiny([snippet support])))
  }

  let camera(p, fill: root-color) = {
    circle(p, radius: .07, fill: fill, stroke: none)
    let (x, y) = p
    line((x, y), (x - .25, y + .34), (x + .25, y + .34), close: true,
      fill: fill.lighten(82%),
      stroke: .44pt + fill)
  }

  let target(x, y) = {
    rect((x - .25, y - .16), (x + .25, y + .16),
      radius: .035,
      fill: target-color.lighten(76%),
      stroke: .55pt + target-color)
    content((x, y), text(size: 6.2pt, [$e$]))
  }

  let obstacle(x, y, w: .6, h: .48) = {
    rect((x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
      radius: .06,
      fill: obstacle-color.lighten(82%),
      stroke: .55pt + obstacle-color)
  }

  let path(a, b, tint, dash: none) = {
    line(a, b,
      stroke: if dash == none { .7pt + tint } else { (paint: tint, thickness: .7pt, dash: dash) },
      mark: arrow-style)
  }

  let root-and-target(x, y) = {
    camera((x + .95, y + 1.22))
    content((x + .78, y + 1.0), tiny([$r_t$]))
    target(x + 3.18, y + 2.78)
  }

  // A: feasible row.
  panel(.0, 4.35, [A. feasible], [$m_(t,i)=1$; scored row], valid-color)
  support(.0, 4.35)
  root-and-target(.0, 4.35)
  path((.95, 5.57), (2.35, 6.62), valid-color)
  camera((2.35, 6.62), fill: valid-color)
  line((2.35, 6.62), (3.18, 7.13), stroke: .48pt + support-color, mark: arrow-style)

  // B: straight-line collision.
  panel(4.75, 4.35, [B. path collision], [$m_(t,i)=0$; $rho_(t,i)="path"$], invalid-color)
  support(4.75, 4.35)
  root-and-target(4.75, 4.35)
  obstacle(6.8, 6.35)
  path((5.7, 5.57), (7.55, 7.0), invalid-color)
  camera((7.55, 7.0), fill: invalid-color)
  content((6.2, 6.78), tiny([blocked segment]))

  // C: insufficient mesh clearance.
  panel(9.5, 4.35, [C. clearance], [$m_(t,i)=0$; $rho_(t,i)="clearance"$], invalid-color)
  support(9.5, 4.35)
  root-and-target(9.5, 4.35)
  obstacle(11.92, 6.62, w: .9, h: .68)
  path((10.45, 5.57), (11.95, 6.64), invalid-color)
  camera((11.95, 6.64), fill: invalid-color)
  circle((11.95, 6.64), radius: .39,
    fill: none,
    stroke: (paint: invalid-color, thickness: .43pt, dash: "dashed"))
  content((10.62, 7.08), tiny([clearance radius]))

  // D: outside support envelope.
  panel(2.35, 0, [D. support], [$m_(t,i)=0$; $rho_(t,i)="support"$], invalid-color)
  support(2.35, 0)
  root-and-target(2.35, 0)
  path((3.3, 1.22), (6.0, 3.55), invalid-color)
  camera((6.0, 3.55), fill: invalid-color)
  content((5.35, 2.82), tiny([outside admissible map]))

  // E: valid but weak utility.
  panel(7.1, 0, [E. weak evidence], [$m_(t,i)=1$; low gain/support], weak-color)
  support(7.1, 0)
  root-and-target(7.1, 0)
  path((8.05, 1.22), (9.4, 1.82), weak-color)
  camera((9.4, 1.82), fill: weak-color)
  line((9.4, 1.82), (10.28, 2.78),
    stroke: (paint: weak-color, thickness: .5pt, dash: "dashed"),
    mark: arrow-style)
  content((8.35, 2.55), tiny([kept as a low-utility row]))
})
