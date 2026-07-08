#import "@preview/cetz:0.5.2"

#set page(width: auto, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.3pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let panel-fill = rgb("#f8fafc")
#let panel-stroke = rgb("#cbd5e1")
#let actor-color = rgb("#2563eb")
#let oracle-color = rgb("#dc2626")
#let gate-color = rgb("#7c3aed")
#let row-color = rgb("#16a34a")
#let eval-color = rgb("#b45309")

#let label(body) = text(size: 7.4pt, body)
#let tiny(body) = text(size: 6.3pt, fill: muted, body)

#cetz.canvas(length: 8mm, padding: .32, {
  import cetz.draw: *

  let arrow-style = (end: ">", scale: .72)
  let dash-arrow = (end: ">", scale: .72)

  let card(x, y, w, h, title, body, tint) = {
    rect((x, y), (x + w, y + h),
      radius: .1,
      fill: tint.lighten(84%),
      stroke: .72pt + tint)
    content((x + w / 2, y + h - .34), align(center, text(size: 7pt, weight: "bold", title)))
    content((x + w / 2, y + h / 2 - .12), align(center, text(size: 6.2pt, fill: ink, body)))
  }

  let gate(x, y, w, h, title, body) = {
    rect((x, y), (x + w, y + h),
      radius: .12,
      fill: gate-color.lighten(86%),
      stroke: .78pt + gate-color)
    content((x + w / 2, y + h - .34), align(center, text(size: 7pt, weight: "bold", title)))
    content((x + w / 2, y + h / 2 - .15), align(center, text(size: 6.15pt, fill: ink, body)))
  }

  let small-obb(x, y, w, h, tint, dash: none, fill-alpha: 88%) = {
    rect((x, y), (x + w, y + h),
      radius: .04,
      fill: tint.lighten(fill-alpha),
      stroke: if dash == none { .66pt + tint } else { (paint: tint, thickness: .66pt, dash: dash) })
  }

  rect((0, 0), (18.6, 7.15),
    radius: .12,
    fill: white,
    stroke: .5pt + rgb("#e2e8f0"))

  content((.45, 6.76), align(left, text(weight: "bold", [Target-task sampler contract])))
  content((.45, 6.38), align(left, tiny([identity and labelability are fixed before rollout labels and headroom are measured])))

  card(.55, 4.65, 3.1, 1.25, [Actor-visible proposal], [
    $hat(bold(B))_(hat(e))$ \
    $bold(phi)_(hat(e))$ + audit fields
  ], actor-color)

  card(.55, 2.75, 3.1, 1.25, [Oracle assets], [
    GT OBB set $cal(E)$ \
    target meshes for labels
  ], oracle-color)

  gate(4.45, 3.58, 3.4, 1.35, [Identity gate], [
    $mu_1 >= tau_"IoU"$ \
    $mu_1 - mu_2 >= tau_"gap"$
  ])

  rect((4.65, .95), (7.65, 2.85),
    radius: .1,
    fill: panel-fill,
    stroke: .65pt + panel-stroke)
  content((6.15, 2.52), align(center, text(size: 6.9pt, weight: "bold", [OBB match inset])))
  small-obb(5.02, 1.42, 1.22, .72, actor-color, dash: "dashed")
  content((4.96, 1.18), tiny([$hat(B)$]))
  small-obb(5.22, 1.55, 1.22, .72, eval-color)
  content((6.52, 2.18), tiny([$B_(e_1)$, $mu_1$]))
  small-obb(6.05, 1.18, .98, .58, muted, dash: "dashed")
  content((7.06, 1.3), tiny([$B_(e_2)$, $mu_2$]))
  small-obb(4.82, 2.17, .65, .35, muted, dash: "dashed")
  content((5.48, 2.28), tiny([$B_(e_3)$]))
  content((6.18, 1.02), tiny([$mu_1 - mu_2$ is the ambiguity gap]))

  card(8.8, 4.25, 3.35, 1.45, [Deterministic cap], [
    select from $cal(E)_"valid"$ \
    seeded uniform/stratified \
    keep unmatched reasons
  ], row-color)

  card(8.8, 2.35, 3.35, 1.35, [Target-task row], [
    $e$, $bold(phi)_e$, match record \
    source, support, distance
  ], row-color)

  card(13.0, 3.55, 2.95, 1.45, [Rollout generation], [
    finite $cal(Q)_t$ \
    masks + reasons
  ], eval-color)

  card(13.0, 1.65, 2.95, 1.35, [GT-EVAL labels], [
    target crop \
    $r_t^e$, $Delta_"look"$
  ], oracle-color)

  card(16.4, 2.65, 1.65, 1.45, [Actor input], [
    target descriptor \
    no GT boxes
  ], actor-color)

  line((3.65, 5.28), (4.43, 4.35), stroke: .82pt + actor-color, mark: arrow-style)
  line((3.65, 3.38), (4.43, 4.02), stroke: .82pt + oracle-color, mark: arrow-style)
  line((7.85, 4.25), (8.78, 4.98), stroke: .82pt + gate-color, mark: arrow-style)
  line((10.48, 4.25), (10.48, 3.72), stroke: .82pt + row-color, mark: arrow-style)
  line((12.15, 3.03), (12.98, 4.2), stroke: .82pt + row-color, mark: arrow-style)
  line((14.48, 3.55), (14.48, 3.02), stroke: .82pt + eval-color, mark: arrow-style)
  line((15.95, 2.32), (16.38, 3.15), stroke: .82pt + actor-color, mark: arrow-style)

  line((.35, .52), (18.25, .52),
    stroke: (paint: muted, thickness: .55pt, dash: "dashed"))
  content((.55, .32), tiny([GT assets and labels are oracle-only; actor inputs keep target descriptors, not GT boxes]))
})
