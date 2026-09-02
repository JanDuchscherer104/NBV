#import "@preview/cetz:0.5.2"

#set page(width: 160mm, height: 72mm, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 8.4pt, fill: rgb("#17202a"))

#let ink = rgb("#17202a")
#let muted = rgb("#687380")
#let guide = rgb("#d4dbe2")
#let retained = rgb("#17748c")
#let ranked = rgb("#b95b08")
#let invalid = rgb("#a43a43")
#let pruned = rgb("#7d8995")

#let temporal-guide(x, label) = {
  import cetz.draw: *
  line(
    (x, .91),
    (x, 4.48),
    stroke: (paint: guide, thickness: .48pt, dash: "dashed"),
  )
  content(
    (x, 4.57),
    text(size: 8.2pt, fill: muted)[#label],
    anchor: "south",
  )
}

#let path-node(point, role: "retained") = {
  import cetz.draw: *
  if role == "root" {
    circle(point, radius: .105, fill: ink, stroke: white + .5pt)
  } else if role == "ranked" {
    circle(point, radius: .13, fill: ranked, stroke: white + .55pt)
  } else {
    circle(point, radius: .12, fill: white, stroke: retained + 1.1pt)
  }
}

#cetz.canvas(length: 14.3mm, padding: .05, {
  import cetz.draw: *

  temporal-guide(1.0, [$t$])
  temporal-guide(4.8, [$t+1$])
  temporal-guide(8.7, [$t+2$])

  // The neutral prefix is factual history; all branches begin at its terminal
  // root. It is deliberately not assigned an oracle score.
  bezier(
    (.05, 2.12),
    (1.0, 2.46),
    (.32, 2.20),
    (.72, 2.38),
    stroke: (paint: ink, thickness: 2.05pt, cap: "round"),
  )
  content((.08, 2.02), text(size: 8pt, weight: "bold")[factual prefix], anchor: "north-west")

  // Two complete retained paths share one factual root. The thinner path wins
  // the immediate ordering; the thicker path ranks first under the scoped
  // two-step return while both complete paths remain retained.
  bezier(
    (1.0, 2.46),
    (4.8, 3.76),
    (2.25, 2.77),
    (3.48, 3.63),
    stroke: (paint: retained, thickness: 1.35pt, cap: "round"),
    name: "tau-1-first",
  )
  bezier(
    (4.8, 3.76),
    (8.7, 3.41),
    (6.05, 3.97),
    (7.55, 3.72),
    stroke: (paint: retained, thickness: 1.35pt, cap: "round"),
    name: "tau-1-second",
  )
  bezier(
    (1.0, 2.46),
    (4.8, 2.42),
    (2.25, 2.18),
    (3.52, 2.24),
    stroke: (paint: ranked, thickness: 2.25pt, cap: "round"),
    name: "tau-2-first",
  )
  bezier(
    (4.8, 2.42),
    (8.7, 2.63),
    (6.05, 2.19),
    (7.55, 2.34),
    stroke: (paint: ranked, thickness: 2.25pt, cap: "round"),
    name: "tau-2-second",
  )

  // Invalid rows terminate before the next time plane; they are never drawn as
  // low-valued successor leaves.
  line(
    (1.0, 2.46),
    (2.02, 3.75),
    stroke: (paint: invalid, thickness: .85pt, dash: "dotted"),
  )
  line((1.88, 3.63), (2.16, 3.87), stroke: invalid + 1.1pt)
  line((1.88, 3.87), (2.16, 3.63), stroke: invalid + 1.1pt)
  content(
    (2.23, 3.75),
    text(size: 8pt, fill: invalid)[invalid row: no child],
    anchor: "west",
  )

  // A legal root row outside the branch factor remains in the full candidate
  // shell but does not become a trajectory. A later expanded trajectory can be
  // removed by the beam. Distinct end marks keep these controls separate.
  line(
    (1.0, 2.46),
    (2.13, 1.42),
    stroke: (paint: pruned, thickness: .85pt, dash: "dashed"),
  )
  line((2.03, 1.34), (2.23, 1.50), stroke: pruned + 1pt)
  line(
    (4.8, 2.42),
    (8.70, 1.46),
    stroke: (paint: pruned, thickness: .85pt, dash: "dashed"),
  )
  line((8.55, 1.34), (8.75, 1.50), stroke: pruned + 1pt)
  line((8.65, 1.42), (8.85, 1.58), stroke: pruned + 1pt)
  content(
    (2.28, 1.35),
    text(size: 7.8pt, fill: pruned)[valid row; not expanded \ stored in full shell],
    anchor: "west",
  )
  content(
    (6.18, 1.18),
    text(size: 7.8pt, fill: pruned)[expanded path; beam-pruned],
    anchor: "west",
  )

  path-node((1.0, 2.46), role: "root")
  path-node((4.8, 3.76))
  path-node((8.7, 3.41))
  path-node((4.8, 2.42), role: "ranked")
  path-node((8.7, 2.63), role: "ranked")
  circle((8.7, 2.63), radius: .27, fill: none, stroke: ink + 1.15pt)

  content((.80, 2.53), text(size: 8.2pt, weight: "bold")[$s_t$], anchor: "east")
  content((2.65, 3.29), text(size: 8.1pt, fill: retained, weight: "bold")[$i_1$], anchor: "south")
  content((2.65, 2.20), text(size: 8.1pt, fill: ranked, weight: "bold")[$i_2$], anchor: "north")
  content((8.94, 3.41), text(size: 8.2pt, fill: retained, weight: "bold")[$tau_1$], anchor: "west")
  content((9.02, 2.63), text(size: 8.2pt, weight: "bold")[$tau_2$], anchor: "west")

  // Symbolic ordering only: no numeric rewards and no learned-policy claim.
  content(
    (4.85, .20),
    text(size: 8.2pt)[
      one-step: $r_t^e(i_1) > r_t^e(i_2)$ $arrow.r$ $i_1$ \
      $h=2$, $gamma=1$: $G_(t,e)^((2))(tau_2) > G_(t,e)^((2))(tau_1)$ $arrow.r$ $tau_2$ ranks first (root action $i_2$)
    ],
    anchor: "south",
  )
})
