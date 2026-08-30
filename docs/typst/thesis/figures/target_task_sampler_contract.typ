#import "@preview/cetz:0.5.2"

#set page(width: 160mm, height: 60mm, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.4pt, fill: rgb("#17202a"))

#let ink = rgb("#17202a")
#let muted = rgb("#687380")
#let rule = rgb("#cbd3dc")
#let eligible = rgb("#17748c")
#let selected = rgb("#b95b08")
#let invalid = rgb("#a43a43")

#let heading(x, title, subtitle, tint: ink) = {
  import cetz.draw: *
  content((x, 5.55), text(size: 8.7pt, weight: "bold", fill: tint)[#title], anchor: "west")
  content((x, 5.15), text(size: 7.55pt, fill: muted)[#subtitle], anchor: "west")
}

#let dot(x, y, label, role: "source") = {
  import cetz.draw: *
  let tint = if role == "eligible" { eligible } else if role == "selected" { selected } else { ink }
  if role == "invalid" {
    line((x - .09, y - .09), (x + .09, y + .09), stroke: 1.05pt + invalid)
    line((x - .09, y + .09), (x + .09, y - .09), stroke: 1.05pt + invalid)
  } else if role == "selected" {
    circle((x, y), radius: .105, fill: selected, stroke: none)
  } else if role == "eligible" {
    circle((x, y), radius: .105, fill: white, stroke: .95pt + eligible)
  } else {
    circle((x, y), radius: .085, fill: ink, stroke: none)
  }
  content((x + .18, y), text(size: 7.9pt, weight: "bold", fill: if role == "invalid" { invalid } else { tint })[#label], anchor: "west")
}

#let rail-arrow(x0, x1, y: 3.70) = {
  import cetz.draw: *
  line((x0, y), (x1, y), stroke: .90pt + ink, mark: (end: ">", scale: .55))
}

#cetz.canvas(length: 8mm, padding: .04, {
  import cetz.draw: *

  content((.42, 6.55), text(size: 8.2pt, weight: "bold")[Privileged oracle V0 — GT only], anchor: "west")
  content((19.55, 6.55), text(size: 8pt, weight: "bold", fill: muted)[actor evidence not read], anchor: "east")
  line((.42, 6.20), (19.55, 6.20), stroke: .48pt + rule)

  // One sparse population rail: construct, classify, sample, persist.
  heading(.42, [Latest GT slice], [last nonempty · padded])
  dot(.62, 3.70, [$e_0$])
  dot(1.34, 3.70, [$e_1$])
  dot(2.06, 3.70, [$e_2$])
  rect((2.78, 3.58), (3.18, 3.82), fill: white, stroke: (paint: muted, thickness: .55pt, dash: "dashed"))
  content((2.98, 3.36), text(size: 7.1pt, fill: muted)[padding], anchor: "north")

  heading(4.20, [Source rows], [all non-padding OBBs])
  dot(4.42, 3.70, [$e_0$])
  dot(5.26, 3.70, [$e_1$])
  dot(6.10, 3.70, [$e_2$])

  heading(7.82, [Validated rows], [`rows` $= cal(R)_s^"geom"$], tint: eligible)
  dot(8.04, 3.70, [$e_0$], role: "eligible")
  dot(8.92, 3.70, [$e_1$], role: "eligible")
  dot(9.80, 3.70, [$e_2$], role: "eligible")

  heading(11.32, [Seeded cap], [uniform draw], tint: selected)
  content((12.44, 3.78), text(size: 8.1pt, weight: "bold")[$pi_"seed"$], anchor: "center")
  content((12.44, 3.32), text(size: 8pt)[$K' = min(K, abs(cal(R)_s^"geom"))$], anchor: "center")

  heading(15.02, [Emit selected rows], [`selected_rows` + provenance], tint: selected)
  dot(15.24, 3.70, [$e_2$], role: "selected")
  content((16.12, 3.70), text(size: 7.8pt)[rank 0], anchor: "west")

  rail-arrow(3.34, 3.98)
  rail-arrow(6.55, 7.60)
  content((7.08, 4.08), text(size: 7.4pt)[all $g(e)=1$], anchor: "south")
  rail-arrow(10.30, 11.08)
  rail-arrow(13.65, 14.78)

  // Invalid geometry is fail-fast: descriptor validation raises before append.
  line((7.08, 3.45), (7.08, 2.24), stroke: (paint: invalid, thickness: .70pt, dash: "dashed"), mark: (end: ">", scale: .48))
  content((7.08, 1.98), align(center, text(size: 7.45pt, fill: invalid)[any $g(e)=0$\
  descriptor raises before result]), anchor: "north")

  // The exact admission predicate is the only secondary annotation.
  content((.42, .82), text(size: 7.45pt, fill: muted)[all-padding block $arrow.r$ no task rows], anchor: "west")
  content((10.05, .82), text(size: 7.8pt)[$g(e) = op("finite")(bold(B)_e) and op("finite")(bold(l)_e) and min(bold(l)_e) > 0$], anchor: "west")
})
