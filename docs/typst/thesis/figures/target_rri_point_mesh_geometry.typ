#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.5pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let mesh-color = rgb("#b45309")
#let point-color = rgb("#2563eb")
#let candidate-color = rgb("#16a34a")
#let acc-color = rgb("#7c3aed")
#let comp-color = rgb("#dc2626")

#let label(body) = text(size: 7.6pt, body)
#let tiny(body) = text(size: 6.7pt, fill: muted, body)

#cetz.canvas(length: 8mm, padding: .2, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .72)
  let dashed-arrow = (end: ">", scale: .72)

  let panel(x, title, subtitle) = {
    rect(
      (x, 0), (x + 8.0, 5.9),
      radius: .12,
      fill: panel-fill,
      stroke: .65pt + panel-stroke,
    )
    content((x + .25, 5.55), align(left, text(weight: "bold", title)))
    content((x + .25, 5.15), align(left, tiny(subtitle)))
  }

  let surface(x) = {
    line((x + 1.1, 2.0), (x + 2.0, 3.0), (x + 3.25, 3.42), (x + 4.65, 3.2), (x + 5.95, 2.55), (x + 6.95, 2.75),
      stroke: 1.1pt + mesh-color)
    for p in ((1.35, 2.22), (2.25, 3.08), (3.35, 3.39), (4.55, 3.22), (5.7, 2.65), (6.65, 2.7)) {
      circle((x + p.at(0), p.at(1)), radius: .055, fill: mesh-color, stroke: none)
    }
    content((x + 6.62, 3.6), label([$cal(M)_e^"GT"$]))
  }

  let point(p, fill) = circle(p, radius: .08, fill: fill, stroke: none)

  panel(0, [A. Before candidate], [$C_e (cal(P)_t)$ has missing target support])
  surface(0)
  for p in ((1.35, 1.75), (2.15, 2.48), (3.15, 2.9), (4.25, 2.72)) {
    point(p, point-color)
  }
  content((1.25, 1.25), label([$C_e(cal(P)_t)$]))
  line((2.15, 2.48), (2.05, 2.93), stroke: .8pt + acc-color, mark: arrow-style)
  content((1.25, 3.45), tiny([$D_(P -> M,t)^e$: accuracy]))
  line((6.65, 2.7), (4.25, 2.72),
    stroke: (paint: comp-color, thickness: .8pt, dash: "dashed"), mark: dashed-arrow)
  content((4.65, 1.95), tiny([$D_(M -> P,t)^e$: completeness]))
  content((2.95, .55), label([$Delta_t^e = D_(P -> M,t)^e + D_(M -> P,t)^e$]))

  panel(8.55, [B. After selected candidate], [$C_e (cal(P)_t union cal(P)_q)$ improves coverage])
  surface(8.55)
  for p in ((9.9, 1.75), (10.7, 2.48), (11.7, 2.9), (12.8, 2.72)) {
    point(p, point-color)
  }
  for p in ((13.55, 2.95), (14.2, 2.65), (15.1, 2.82)) {
    point(p, candidate-color)
  }
  content((9.55, 1.25), label([$C_e(cal(P)_t)$]))
  content((13.35, 1.95), label([$C_e(cal(P)_q)$]))
  line((10.7, 2.48), (10.6, 2.95), stroke: .8pt + acc-color, mark: arrow-style)
  line((15.2, 2.82), (15.2, 2.72), stroke: .8pt + acc-color, mark: arrow-style)
  line((15.2, 2.72), (15.1, 2.82),
    stroke: (paint: comp-color, thickness: .8pt, dash: "dashed"), mark: dashed-arrow)
  line((14.25, 2.65), (14.2, 2.65),
    stroke: (paint: comp-color, thickness: .8pt, dash: "dashed"), mark: dashed-arrow)
  content((12.05, .55), label([$Delta_(t+1)^e < Delta_t^e$]))

  line((7.55, 2.95), (8.35, 2.95), stroke: 1pt + ink, mark: arrow-style)
  content((6.35, -.45), label([$r_t^e = (Delta_t^e - Delta_(t+1)^e) / (Delta_0^e + epsilon)$]))
})
