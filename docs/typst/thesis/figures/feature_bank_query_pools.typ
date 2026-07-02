#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.2pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let point-color = rgb("#2563eb")
#let dino-color = rgb("#7c3aed")
#let target-color = rgb("#b45309")
#let frustum-color = rgb("#16a34a")
#let ray-color = rgb("#0891b2")
#let evl-color = rgb("#dc2626")

#let label(body) = text(size: 7.4pt, body)
#let tiny(body) = text(size: 6.4pt, fill: muted, body)

#cetz.canvas(length: 8mm, padding: .32, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .72)
  let panel(x, title, subtitle) = {
    rect(
      (x, 0), (x + 7.85, 6.25),
      radius: .12,
      fill: panel-fill,
      stroke: .65pt + panel-stroke,
    )
    content((x + .25, 5.9), align(left, text(weight: "bold", title)))
    content((x + .25, 5.5), align(left, tiny(subtitle)))
  }
  let token(x, y, title, body, tint) = {
    rect((x, y), (x + 2.35, y + .86),
      radius: .08,
      fill: tint.lighten(82%),
      stroke: .62pt + tint)
    content((x + 1.18, y + .58), align(center, text(size: 6.8pt, weight: "bold", title)))
    content((x + 1.18, y + .24), align(center, text(size: 5.8pt, fill: ink, body)))
  }
  let point(p, tint: point-color, r: .065) = circle(p, radius: r, fill: tint, stroke: none)
  let target-box(x, y, w: 1.55, h: 1.0) = {
    rect((x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
      radius: .06,
      fill: target-color.lighten(82%),
      stroke: 1pt + target-color)
    content((x, y + .68), tiny([target OBB]))
  }
  let frustum(c, a, b) = {
    line(c, a, b, close: true,
      fill: frustum-color.lighten(88%),
      stroke: .85pt + frustum-color)
    circle(c, radius: .09, fill: frustum-color, stroke: none)
    content((c.at(0) - .12, c.at(1) - .34), tiny([$q_(t,i)$]))
  }

  panel(0, [A. Actor-visible feature bank], [carriers retain source and visibility provenance])
  for p in ((.8, 1.35), (1.25, 2.35), (1.85, 1.72), (2.35, 2.8), (2.9, 1.2), (3.4, 2.22), (4.05, 3.0), (4.6, 1.75)) {
    point(p)
  }
  line((.62, 1.02), (1.32, 2.42), (2.38, 2.94), (3.45, 2.26), (4.72, 1.66),
    stroke: (paint: point-color.lighten(20%), thickness: .55pt, dash: "dashed"))
  content((.7, 3.55), label([$bold(X)_t^"pt"$]))
  content((2.05, .72), tiny([semidense/fused world points]))

  token(5.05, 4.15, [$bold(F)_t^"DINO@pt"$], [logged, compressed], dino-color)
  token(5.05, 3.05, [$bold(M)_t^"ray"$], [occ/free/unknown], ray-color)
  token(5.05, 1.95, [$bold(E)_0^"EVL-local"$], [finite support], evl-color)
  token(5.05, .85, [masks], [missing modality], muted)
  line((4.35, 2.35), (5.02, 4.56), stroke: .72pt + muted, mark: arrow-style)
  line((4.35, 2.35), (5.02, 3.48), stroke: .72pt + muted, mark: arrow-style)
  line((4.35, 2.35), (5.02, 2.38), stroke: .72pt + muted, mark: arrow-style)
  line((4.35, 2.35), (5.02, 1.28), stroke: .72pt + muted, mark: arrow-style)
  content((2.82, 5.02), tiny([point carrier + source tags]))

  panel(8.35, [B. Query pools], [same bank, different spatial predicates])
  let c = (9.35, 1.1)
  frustum(c, (10.55, 4.95), (14.7, 3.2))
  target-box(12.2, 3.35)
  rect((11.42, 2.85), (12.98, 3.85),
    radius: .06,
    fill: target-color.lighten(88%),
    stroke: (paint: target-color, thickness: .7pt, dash: "dashed"))
  line((11.42, 2.85), (12.98, 3.85),
    stroke: (paint: target-color, thickness: .45pt, dash: "dashed"))
  content((13.52, 4.35), tiny([$hat(bold(B))_e$]))
  content((10.0, 4.95), tiny([candidate frustum]))

  for p in ((11.7, 3.05), (12.0, 3.45), (12.38, 3.18), (12.62, 3.7)) {
    point(p, tint: target-color)
  }
  for p in ((10.65, 2.15), (11.35, 2.35), (13.2, 2.92), (13.75, 3.05), (14.2, 2.6)) {
    point(p, tint: frustum-color)
  }
  for p in ((12.18, 3.05), (12.42, 3.42)) {
    circle(p, radius: .105, fill: dino-color, stroke: .45pt + ink)
  }
  for p in ((9.6, 4.8), (13.9, 1.45), (14.6, 4.75)) {
    point(p, tint: muted, r: .052)
  }
  content((13.15, .62), tiny([outside query: retained, not pooled]))

  token(16.0, 4.45, [$bold(g)_e^"tgt"$], [points in OBB], target-color)
  token(16.0, 3.15, [$bold(g)_(t,i)^"fr"$], [points in frustum], frustum-color)
  token(16.0, 1.85, [$bold(g)_(t,e,i)^"cap"$], [OBB ∩ frustum], dino-color)
  token(16.0, .55, [$bold(g)_(t,i)^"ray"$], [render/query], ray-color)

  line((12.2, 3.35), (15.95, 4.88), stroke: .8pt + target-color, mark: arrow-style)
  line((12.95, 2.75), (15.95, 3.58), stroke: .8pt + frustum-color, mark: arrow-style)
  line((12.32, 3.25), (15.95, 2.28), stroke: .8pt + dino-color, mark: arrow-style)
  line((9.35, 1.1), (15.95, .98), stroke: .8pt + ray-color, mark: arrow-style)
})
