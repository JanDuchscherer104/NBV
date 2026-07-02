#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let root-color = rgb("#2563eb")
#let target-color = rgb("#b45309")
#let forward-color = rgb("#16a34a")
#let bearing-color = rgb("#9333ea")
#let bypass-color = rgb("#dc2626")
#let ray-color = rgb("#0891b2")

#let label(body) = text(size: 7.2pt, body)
#let tiny(body) = text(size: 6.3pt, fill: muted, body)

#cetz.canvas(length: 8mm, padding: .2, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .75)
  let panel(x, title) = {
    rect(
      (x, 0), (x + 6.1, 6.3),
      radius: .12,
      fill: panel-fill,
      stroke: .65pt + panel-stroke,
    )
    content((x + .25, 5.95), align(left, text(weight: "bold", title)))
  }
  let dot(p, fill) = circle(p, radius: .07, fill: fill, stroke: none)
  let target-box(x, y, w: .72, h: .46) = {
    rect((x - w / 2, y - h / 2), (x + w / 2, y + h / 2),
      radius: .04, fill: target-color.lighten(72%),
      stroke: .75pt + target-color)
    content((x, y), label([$e$]))
  }
  let camera(center, angle: 0deg, tint: root-color) = {
    circle(center, radius: .1, fill: tint, stroke: none)
    let (x, y) = center
    line((x, y), (x - .42, y + .55), (x + .42, y + .55), close: true,
      fill: tint.lighten(78%), stroke: .65pt + tint)
  }

  panel(0, [A. Reference-frame cap])
  let o = (1.15, 1.05)
  dot(o, root-color)
  content((.85, .72), tiny([$r_t$]))
  line(o, (1.15, 4.7), stroke: .9pt + forward-color, mark: arrow-style)
  content((1.45, 4.55), label([$bold(f)$]))
  line(o, (4.55, 3.95), stroke: .9pt + bearing-color, mark: arrow-style)
  content((4.68, 3.95), label([$bold(b)_e$]))
  arc(o, start: 63deg, delta: 45deg, radius: 2.45,
    stroke: (paint: muted, thickness: .55pt, dash: "dashed"))
  content((2.38, 3.72), tiny([azimuth/elevation cap]))
  line(o, (2.75, 3.05), stroke: 1pt + ink, mark: arrow-style)
  content((2.95, 3.05), label([$tilde(bold(u))$]))
  target-box(4.7, 4.35)
  content((.55, 5.25), tiny([sample in the rig-local gauge]))

  panel(6.55, [B. Three center families])
  let r = (7.45, 1.05)
  let tgt = (10.95, 4.15)
  dot(r, root-color)
  content((7.13, .72), tiny([$r_t$]))
  target-box(tgt.at(0), tgt.at(1))
  line(r, (7.45, 3.45), stroke: .9pt + forward-color, mark: arrow-style)
  dot((7.45, 3.45), forward-color)
  content((7.85, 3.45), label([`forward_local`]))
  line(r, (9.7, 3.15), stroke: .9pt + bearing-color, mark: arrow-style)
  dot((9.7, 3.15), bearing-color)
  content((8.05, 2.7), label([`target_bearing`]))
  line(r, (11.2, 2.05), stroke: .9pt + bypass-color, mark: arrow-style)
  dot((11.2, 2.05), bypass-color)
  content((9.65, 1.62), label([`lateral_bypass`]))
  line((10.95, 4.15), (11.2, 2.05),
    stroke: (paint: bypass-color, thickness: .55pt, dash: "dashed"))
  content((9.45, 5.25), tiny([same radius shell, different semantic axes]))

  panel(13.1, [C. Target-look camera])
  let c = (14.55, 1.2)
  let pe = (17.35, 4.1)
  camera(c, tint: root-color)
  target-box(pe.at(0), pe.at(1))
  line(c, pe, stroke: 1pt + ray-color, mark: arrow-style)
  content((16.05, 2.65), label([$bold(z)_"cam" -> bold(p)_e$]))
  line(c, (13.8, 3.1), stroke: .75pt + muted)
  line(c, (15.8, 3.05), stroke: .75pt + muted)
  line((13.8, 3.1), (15.8, 3.05),
    stroke: (paint: muted, thickness: .5pt, dash: "dashed"))
  content((14.75, .72), tiny([$bold(c)_(t,i)$]))
  content((16.6, 5.2), tiny([frustum-target relation]))
  line((14.55, 1.2), (15.65, 1.2), stroke: .8pt + root-color, mark: arrow-style)
  content((15.85, 1.2), tiny([$bold(x)_c$]))
  line((14.55, 1.2), (14.55, 2.15), stroke: .8pt + root-color, mark: arrow-style)
  content((14.7, 2.22), tiny([$bold(y)_c$]))
})
