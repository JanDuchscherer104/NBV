#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.4pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let camera-color = rgb("#2563eb")
#let ray-color = rgb("#0891b2")
#let mesh-color = rgb("#b45309")
#let point-color = rgb("#16a34a")
#let crop-color = rgb("#7c3aed")

#let label(body) = text(size: 7.4pt, body)
#let tiny(body) = text(size: 6.5pt, fill: muted, body)

#cetz.canvas(length: 8mm, padding: .45, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .72)
  let panel(y, title, subtitle) = {
    rect(
      (0, y), (8.45, y + 4.45),
      radius: .12,
      fill: panel-fill,
      stroke: .65pt + panel-stroke,
    )
    content((3.45, y + 4.12), align(left, text(weight: "bold", title)))
    content((3.45, y + 3.74), align(left, tiny(subtitle)))
  }
  let camera(center, tint: camera-color) = {
    let (x, y) = center
    circle(center, radius: .11, fill: tint, stroke: none)
    line((x, y), (x - .48, y + .6), (x + .48, y + .6), close: true,
      fill: tint.lighten(82%), stroke: .65pt + tint)
  }

  panel(4.75, [A. Candidate camera convention], [LUF axes and mesh-rendered depth])
  let c = (1.15, 5.65)
  camera(c)
  content((.55, 5.25), label([$c_q$]))
  line(c, (.35, 5.65), stroke: .85pt + camera-color, mark: arrow-style)
  content((.18, 5.38), tiny([$+x$: left]))
  line(c, (1.15, 6.45), stroke: .85pt + camera-color, mark: arrow-style)
  content((1.3, 6.48), tiny([$+y$: up]))
  line(c, (2.05, 5.98), stroke: .85pt + camera-color, mark: arrow-style)
  content((2.18, 5.98), tiny([$+z$: forward]))
  line(c, (3.0, 7.55), stroke: .85pt + ray-color)
  line(c, (4.0, 7.12), stroke: .85pt + ray-color)
  line((3.0, 7.55), (4.0, 7.12), stroke: .65pt + muted)
  content((3.08, 7.78), tiny([image plane]))
  circle((3.52, 7.34), radius: .05, fill: ray-color, stroke: none)
  line((3.52, 7.34), (6.15, 7.03),
    stroke: (paint: ray-color, thickness: .75pt, dash: "dashed"), mark: arrow-style)
  content((3.35, 6.92), label([$bold(D)_q(u,v)$]))
  line((5.2, 6.25), (5.75, 7.0), (6.45, 7.25), (7.25, 6.88),
    stroke: 1.1pt + mesh-color)
  content((6.15, 7.55), label([$cal(M)^"GT"$]))
  content((4.2, 5.18), tiny([render with calibrated intrinsics and pose]))

  panel(0, [B. Ray unprojection and target crop], [pixels become world points before target scoring])
  rect((.55, 2.55), (1.8, 3.45), radius: .04,
    fill: ray-color.lighten(84%), stroke: .6pt + ray-color)
  for x in (.86, 1.18, 1.5) {
    line((x, 2.55), (x, 3.45), stroke: .35pt + ray-color.lighten(30%))
  }
  for y in (2.84, 3.14) {
    line((.55, y), (1.8, y), stroke: .35pt + ray-color.lighten(30%))
  }
  circle((1.18, 3.14), radius: .055, fill: camera-color, stroke: none)
  content((.85, 3.26), tiny([$(u,v)$]))
  line((1.18, 3.14), (2.85, 2.5), stroke: .9pt + ray-color, mark: arrow-style)
  content((1.55, 2.66), tiny([$bold(x)_c = D_q K^(-1)[u,v,1]$]))
  line((2.85, 2.5), (3.7, 2.5), stroke: .9pt + ink, mark: arrow-style)
  content((2.95, 2.82), tiny([$bold(T)_(w,c_q)$]))
  for p in ((4.45, 2.15), (4.85, 2.5), (5.45, 2.78), (5.95, 2.48)) {
    circle(p, radius: .07, fill: point-color, stroke: none)
  }
  rect((4.15, 1.62), (6.35, 3.08), radius: .1,
    fill: none, stroke: (paint: crop-color, thickness: .75pt, dash: "dashed"))
  line((4.0, 1.42), (4.65, 2.15), (5.6, 2.55), (7.1, 2.15),
    stroke: 1.05pt + mesh-color)
  content((5.85, 3.34), label([$C_e(cal(P)_t union cal(P)_q)$]))
  content((4.05, 1.02), label([$cal(P)_q$ in world frame]))
  content((6.05, 1.45), label([$cal(M)_e^"GT"$]))
  content((1.95, .62), label([$bold(x)_w = bold(T)_(w,c_q) bold(x)_c$]))
})
