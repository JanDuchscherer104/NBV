#import "@preview/fletcher:0.5.8": diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 8.8pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let blue = rgb("#2563eb")
#let green = rgb("#16a34a")
#let amber = rgb("#b45309")
#let violet = rgb("#7c3aed")
#let slate = rgb("#475569")

#let axis(pos, title, subtitle, levels, tint) = node(
  pos,
  align(left)[
    #text(weight: "bold", size: 8.8pt, fill: tint.darken(10%))[#title] \
    #text(size: 6.7pt, fill: muted)[#subtitle]
    #v(3pt)
    #for (index, level) in levels.enumerate() {
      box(
        width: 34mm,
        inset: 3pt,
        radius: 2pt,
        fill: if index == levels.len() - 1 { tint.lighten(87%) } else { white },
        stroke: .55pt + tint.lighten(if index == levels.len() - 1 { 8% } else { 55% }),
      )[
        #text(size: 7.1pt, weight: if index == levels.len() - 1 { "bold" } else { "regular" }, fill: ink)[#level]
      ]
      if index < levels.len() - 1 { v(2pt) }
    }
  ],
  width: 39mm,
  inset: 5pt,
  fill: rgb("#f8fafc"),
  stroke: .75pt + tint.lighten(22%),
  corner-radius: 3pt,
)

#let arrow(from, to, tint: muted) = edge(
  from,
  to,
  "-|>",
  stroke: .8pt + tint,
)

#diagram(
  spacing: 8pt,
  cell-size: (42mm, 15mm),
  edge-stroke: .8pt + muted,
  edge-corner-radius: 3pt,
  mark-scale: 70%,

  node(
    (1.5, 0),
    align(center)[
      #text(weight: "bold", size: 10.2pt, fill: ink)[Next-best-view methods occupy a multi-axis design space]
      #v(2pt)
      #text(size: 7.1pt, fill: muted)[The axes describe what is optimized, where the target comes from, how actions are supported, and what state is represented.]
    ],
    width: 150mm,
    inset: 6pt,
    fill: rgb("#f1f5f9"),
    stroke: 1pt + slate,
    corner-radius: 3pt,
  ),

  axis((0, 1.5), [Utility], [objective], (
    [coverage / visibility],
    [uncertainty / information],
    [scene-wide reconstruction],
    [target-specific quality],
  ), blue),
  axis((1.0, 1.5), [Target source], [conditioning signal], (
    [scene-wide objective],
    [oracle-defined target],
    [actor-observed target],
    [target + identity context],
  ), amber),
  axis((2.0, 1.5), [Action / horizon], [decision support], (
    [single greedy view],
    [finite candidate set],
    [bounded lookahead],
    [continuous / hierarchical control],
  ), green),
  axis((3.0, 1.5), [Representation], [state evidence], (
    [point / surface],
    [occupancy / ray grid],
    [radiance field / 3DGS],
    [egocentric foundation evidence],
  ), violet),

  node(
    (1.5, 5.0),
    align(center)[
      #text(weight: "bold", size: 8.4pt, fill: slate)[ARIA-NBV position]
      #v(2pt)
      #text(size: 7pt, fill: ink)[finite candidates · target-quality utility · actor/oracle-separated target source · egocentric state]
    ],
    width: 112mm,
    inset: 5pt,
    fill: violet.lighten(92%),
    stroke: .9pt + violet,
    corner-radius: 3pt,
  ),

  arrow((1.5, 0), (0, 1.5), tint: blue.lighten(18%)),
  arrow((1.5, 0), (1.0, 1.5), tint: amber.lighten(18%)),
  arrow((1.5, 0), (2.0, 1.5), tint: green.lighten(18%)),
  arrow((1.5, 0), (3.0, 1.5), tint: violet.lighten(18%)),
  arrow((0, 1.5), (1.5, 5.0), tint: blue.lighten(18%)),
  arrow((1.0, 1.5), (1.5, 5.0), tint: amber.lighten(18%)),
  arrow((2.0, 1.5), (1.5, 5.0), tint: green.lighten(18%)),
  arrow((3.0, 1.5), (1.5, 5.0), tint: violet.lighten(18%)),
)
