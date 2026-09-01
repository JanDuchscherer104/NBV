#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: 160mm, height: 88mm, margin: 1.5mm, fill: white)
#set text(font: "New Computer Modern", size: 8.5pt, fill: rgb("#17202a"))

#let ink = rgb("#17202a")
#let muted = rgb("#52606d")
#let foundation = rgb("#9a5a13")
#let oracle = rgb("#6d45a8")
#let actor = rgb("#2563a6")
#let outcome = rgb("#187246")
#let neutral-fill = rgb("#f5f7fa")

#let gate(pos, number, title, evidence, tint, name) = node(
  pos,
  align(left)[
    #text(size: 7.1pt, weight: "bold", fill: tint)[G#number] \
    #text(size: 8pt, weight: "bold", fill: ink)[#title] \
    #text(size: 7.1pt, fill: muted)[#evidence]
  ],
  name: name,
  width: 31mm,
  height: 17mm,
  inset: 5pt,
  fill: tint.lighten(95%),
  stroke: .9pt + tint,
  corner-radius: 3pt,
)

#let and-node(pos, name) = node(
  pos,
  text(size: 6.5pt, weight: "bold", fill: ink)[AND],
  name: name,
  radius: 4.1mm,
  fill: white,
  stroke: 1pt + ink,
)

#let lane-title(pos, body, width) = node(
  pos,
  text(size: 7pt, weight: "bold", fill: muted)[#upper(body)],
  width: width,
  inset: 0pt,
  stroke: none,
)

#let relation(from, to, label: none) = edge(
  from,
  to,
  "-|>",
  label: if label == none { none } else { text(size: 6.7pt, fill: muted)[#label] },
  label-fill: white,
  stroke: .95pt + muted,
)

#diagram(
  spacing: 4pt,
  cell-size: (18.5mm, 12mm),
  edge-stroke: .95pt + muted,
  edge-corner-radius: 3pt,
  mark-scale: 70%,

  lane-title((.3, -.85), [shared foundations], 48mm),
  lane-title((1.6, -.85), [parallel claim paths], 55mm),
  lane-title((2.5, -.85), [RQ2 convergence], 31mm),

  gate(
    (0, 0),
    [1],
    [Measurement validity],
    [repeatability statistic + decision],
    foundation,
    <g1>,
  ),
  gate(
    (0, 1.5),
    [2],
    [Population / action],
    [held-out coverage + support decision],
    foundation,
    <g2>,
  ),
  and-node((.55, .75), <foundation-and>),

  gate(
    (1.2, 0),
    [3],
    [Oracle headroom],
    [paired held-out endpoint effect],
    oracle,
    <g3>,
  ),
  gate(
    (1.2, 1.5),
    [4],
    [Actor-visible $Q_1$],
    [target / mask / history; ranking + calibration],
    actor,
    <g4>,
  ),
  gate(
    (1.95, 1.5),
    [5],
    [$Q_2$ agreement],
    [learned vs. exact recursion + complete support],
    actor,
    <g5>,
  ),

  and-node((2.5, .75), <recovery-and>),
  gate(
    (2.5, 2.85),
    [6],
    [Endpoint recovery],
    [paired recovered-headroom decision],
    outcome,
    <g6>,
  ),

  relation(<g1.east>, <foundation-and.north-west>),
  relation(<g2.east>, <foundation-and.south-west>),
  relation(<foundation-and.north-east>, <g3.west>),
  relation(<foundation-and.south-east>, <g4.west>),
  relation(<g4.east>, <g5.west>),
  relation(<g3.east>, <recovery-and.north-west>),
  relation(<g5.east>, <recovery-and.south-west>),
  relation(<recovery-and.south>, <g6.north>, label: [both pass]),

  node(
    (.65, 4.25),
    align(center)[
      #text(size: 7.4pt, weight: "bold", fill: ink)[Evidence state — reported] \
      #text(size: 7.2pt, fill: muted)[? unavailable  |  × measured non-pass  |  ✓ pass]
    ],
    width: 64mm,
    inset: 5pt,
    fill: neutral-fill,
    stroke: (paint: muted, thickness: .75pt, dash: "dashed"),
    corner-radius: 3pt,
  ),
  node(
    (2.2, 4.25),
    align(center)[
      #text(size: 7.4pt, weight: "bold", fill: ink)[Claim state — derived] \
      #text(size: 7.2pt, fill: muted)[admissible iff own gate + all predecessors pass]
    ],
    width: 66mm,
    inset: 5pt,
    fill: neutral-fill,
    stroke: .75pt + muted,
    corner-radius: 3pt,
  ),
  node(
    (1.43, 4.25),
    text(size: 11pt, weight: "bold", fill: ink)[$!=$],
    width: 8mm,
    inset: 0pt,
    stroke: none,
  ),
)
