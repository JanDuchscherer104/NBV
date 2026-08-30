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

  // One sparse population rail after latest-slice selection and padding removal.
  heading(.42, [Source rows], [latest · unpadded])
  dot(.62, 3.70, [$e_0$])
  dot(1.40, 3.70, [$e_1$])
  dot(2.18, 3.70, [$e_2$])

  heading(4.08, [Set status], [finite + extents $> 0$], tint: eligible)
  dot(4.30, 3.70, [$e_0$], role: "eligible")
  dot(5.08, 3.70, [$e_1$], role: "invalid")
  dot(5.86, 3.70, [$e_2$], role: "eligible")

  heading(7.72, [Append `rows`], [descriptor built], tint: eligible)
  dot(7.94, 3.70, [$e_0$], role: "eligible")
  dot(8.72, 3.70, [$e_1$], role: "invalid")
  dot(9.50, 3.70, [$e_2$], role: "eligible")

  heading(11.34, [Seeded cap], [matched only], tint: selected)
  content((12.48, 3.78), text(size: 8.1pt, weight: "bold")[$pi_"seed"$], anchor: "center")
  content((12.48, 3.32), text(size: 8pt)[$K' = min(K, abs("matched rows"))$], anchor: "center")

  heading(15.08, [Emit selected rows], [rank + provenance], tint: selected)
  dot(15.30, 3.70, [$e_2$], role: "selected")
  content((16.18, 3.70), text(size: 7.8pt)[rank 0], anchor: "west")

  rail-arrow(2.78, 3.82)
  rail-arrow(6.34, 7.46)
  content((6.90, 4.08), text(size: 7.25pt)[descriptor succeeds], anchor: "south")
  rail-arrow(10.06, 11.10)
  content((10.58, 4.08), text(size: 7.25pt, fill: eligible)[○ matched only], anchor: "south")
  rail-arrow(13.70, 14.84)

  // Status is computed first; descriptor-invalid geometry then aborts before append.
  line((6.90, 3.45), (6.90, 1.92), stroke: (paint: invalid, thickness: .70pt, dash: "dashed"), mark: (end: ">", scale: .48))
  content((6.90, 1.68), align(center, text(size: 7.35pt, fill: invalid)[descriptor fails\
  raise before append]), anchor: "north")

  // A descriptor-constructible auxiliary failure remains in rows but cannot reach the cap.
  line((8.72, 3.47), (8.72, 2.72), stroke: (paint: invalid, thickness: .70pt, dash: "dashed"), mark: (end: ">", scale: .46))
  content((8.92, 2.50), text(size: 7.05pt, fill: invalid)[$times$ auxiliary-invalid: retained; excluded from cap], anchor: "west")

  // Sparse edge-case note keeps the slice fallback explicit.
  content((.42, .82), text(size: 7.45pt, fill: muted)[all-padding block $arrow.r$ no task rows], anchor: "west")
})
