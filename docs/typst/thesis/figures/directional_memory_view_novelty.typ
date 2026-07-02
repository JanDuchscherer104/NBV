#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let target-color = rgb("#b45309")
#let history-color = rgb("#2563eb")
#let moment-color = rgb("#7c3aed")
#let cand-color = rgb("#16a34a")
#let novelty-color = rgb("#dc2626")

#let label(body) = text(size: 7.1pt, body)
#let tiny(body) = text(size: 6.2pt, fill: muted, body)
#let formula(body) = text(size: 6.8pt, body)

#cetz.canvas(length: 8mm, padding: .28, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .72)
  let panel(x, title, subtitle) = {
    rect(
      (x, 0), (x + 6.05, 6.45),
      radius: .12,
      fill: panel-fill,
      stroke: .65pt + panel-stroke,
    )
    content((x + .25, 6.08), align(left, text(weight: "bold", title)))
    content((x + .25, 5.68), align(left, tiny(subtitle)))
  }
  let camera(p, tint: history-color, name: none) = {
    circle(p, radius: .095, fill: tint, stroke: none)
    line(p, (p.at(0) - .34, p.at(1) + .34), (p.at(0) + .34, p.at(1) + .34),
      close: true,
      fill: tint.lighten(80%),
      stroke: .55pt + tint)
    if name != none {
      content((p.at(0), p.at(1) - .35), tiny(name))
    }
  }
  let target(p, name: [$bold(v)$]) = {
    circle(p, radius: .13, fill: target-color, stroke: .4pt + ink)
    content((p.at(0) + .25, p.at(1) + .1), label(name))
  }
  let dir-line(a, b, tint: history-color, dashed: false) = {
    line(a, b,
      stroke: (paint: tint, thickness: .8pt, dash: if dashed { "dashed" } else { () }),
      mark: arrow-style)
  }
  let sphere(cx, cy, tint: muted) = {
    circle((cx, cy), radius: 1.42, fill: white, stroke: .75pt + tint)
    line((cx - 1.18, cy + .18), (cx - .5, cy + .4), (cx + .5, cy + .4), (cx + 1.18, cy + .18),
      stroke: (paint: tint.lighten(10%), thickness: .48pt, dash: "dashed"))
    line((cx - 1.18, cy - .18), (cx - .5, cy - .4), (cx + .5, cy - .4), (cx + 1.18, cy - .18),
      stroke: (paint: tint.lighten(10%), thickness: .48pt, dash: "dashed"))
    line((cx - 1.42, cy), (cx + 1.42, cy),
      stroke: (paint: tint.lighten(10%), thickness: .45pt, dash: "dashed"))
    line((cx, cy - 1.42), (cx, cy + 1.42),
      stroke: (paint: tint.lighten(10%), thickness: .45pt, dash: "dashed"))
  }
  let token(x, y, title, body, tint) = {
    rect((x, y), (x + 2.55, y + .88),
      radius: .08,
      fill: tint.lighten(84%),
      stroke: .62pt + tint)
    content((x + 1.27, y + .58), align(center, text(size: 6.7pt, weight: "bold", title)))
    content((x + 1.27, y + .24), align(center, text(size: 5.8pt, fill: ink, body)))
  }

  panel(0, [A. Target-local observations], [history lives around points, not in pose tokens])
  let v = (3.05, 2.65)
  target(v)
  for c in ((.95, 1.15), (1.55, 4.75), (4.95, 4.6), (5.15, 1.35)) {
    camera(c)
    dir-line(v, c)
  }
  content((.7, .68), tiny([$bold(c)_0$]))
  content((1.38, 5.18), tiny([$bold(c)_1$]))
  content((4.9, 5.04), tiny([$bold(c)_2$]))
  content((5.04, .86), tiny([$bold(c)_3$]))
  content((2.18, 4.18), formula([$bold(d)_o(bold(v)) in bb(S)^2$]))
  content((.7, 5.28), tiny([selected camera centers only]))

  panel(6.45, [B. Directional memory], [store a distribution over directions])
  sphere(9.47, 3.18, tint: moment-color)
  for p in ((8.65, 2.5), (8.9, 3.75), (9.85, 4.15), (10.25, 2.3)) {
    circle(p, radius: .08, fill: history-color, stroke: none)
  }
  content((9.47, 4.92), label([$bb(S)^2$]))
  token(6.95, 1.18, [$bold(mu)_t(bold(v))$], [mean direction], moment-color)
  token(9.95, 1.18, [$bold(M)_t(bold(v))$], [second moment], moment-color)
  content((7.0, 5.22), formula([$sum_o w_o bold(d)_o bold(d)_o^top$]))
  content((7.72, .62), tiny([or low-order $Y_(ell m)$ coefficients when ablated]))
  line((8.7, 2.35), (8.18, 2.04), stroke: .62pt + moment-color, mark: arrow-style)
  line((10.15, 2.28), (11.05, 2.04), stroke: .62pt + moment-color, mark: arrow-style)

  panel(12.9, [C. Candidate query], [read novelty from the proposed view])
  let vc = (15.8, 2.55)
  target(vc, name: [$bold(v)$])
  camera((14.05, 1.05), tint: history-color, name: [`old`])
  camera((17.65, 1.05), tint: history-color, name: [`old`])
  camera((17.5, 4.8), tint: cand-color, name: [$q_(t,i)$])
  dir-line(vc, (14.05, 1.05), tint: history-color)
  dir-line(vc, (17.65, 1.05), tint: history-color)
  dir-line(vc, (17.5, 4.8), tint: cand-color)
  arc(vc, start: 39deg, delta: 58deg, radius: 1.18,
    stroke: (paint: novelty-color, thickness: .72pt, dash: "dashed"))
  content((16.95, 3.65), formula([$Delta_"dir"$]))
  token(13.25, 4.24, [$bold(d)_i(bold(v))$], [candidate direction], cand-color)
  token(16.15, .42, [$nu_(t,i)(bold(v))$], [view novelty], novelty-color)
  line((16.55, 3.94), (17.02, 3.8), stroke: .6pt + cand-color, mark: arrow-style)
  line((16.9, 1.45), (16.8, 1.3), stroke: .6pt + novelty-color, mark: arrow-style)
  content((13.22, 5.42), tiny([added to candidate row, not a new observation]))
})
