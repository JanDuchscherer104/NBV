#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let validity = rgb("#b45309")
#let oracle = rgb("#7c3aed")
#let actor = rgb("#2563eb")
#let outcome = rgb("#15803d")

#let gate(pos, number, title, evidence, tint, width: 51mm) = node(
  pos,
  align(left)[
    #text(size: 6.4pt, weight: "bold", fill: tint)[GATE #number] \
    #text(size: 8.0pt, weight: "bold", fill: ink)[#title] \
    #text(size: 6.7pt, fill: muted)[#evidence]
  ],
  width: width,
  inset: 6pt,
  fill: tint.lighten(95%),
  stroke: .85pt + tint,
  corner-radius: 3pt,
)

#let flow(from, to, label: none, bend: 0deg) = edge(
  from,
  to,
  "-|>",
  bend: bend,
  label: if label == none { none } else { text(size: 6.3pt, fill: muted)[#label] },
  label-fill: white,
  stroke: .9pt + muted,
)

#diagram(
  spacing: 8pt,
  cell-size: (55mm, 19mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 4pt,
  mark-scale: 72%,

  gate((0, 0), [1], [Measurement validity], [frozen metric identity; repeatability within tolerance], validity),
  gate((1.5, 0), [2], [Population and action support], [held-out scenes; admitted targets; complete hard-valid tables], validity),
  gate((0, 1.5), [3], [Actor-visible protocol], [match failures / attempts; actor-input identity; leakage audit], actor),
  gate((1.5, 1.5), [4], [Oracle headroom], [equal-budget lookahead versus one-step oracle greedy], oracle),
  gate((0, 3), [5], [Actor-visible $Q_1$], [scene-clustered ranking and calibration intervals], actor),
  gate((0, 4.5), [6], [Exact $Q_2$], [held-out recursive error and complete-support coverage], actor),
  gate((1.5, 4.5), [7], [Endpoint gap closure], [paired learned-myopic, finite-horizon learned, and oracle-lookahead endpoints], outcome),

  node(
    (.75, 5.95),
    align(center)[
      #text(size: 7.2pt, weight: "bold", fill: ink)[Interpret each claim's earliest failed prerequisites] \
      #text(size: 6.7pt, fill: muted)[Its own estimate remains visible; dependent claims are blocked, and missing evidence is never recorded as zero.]
    ],
    width: 126mm,
    inset: 6pt,
    fill: rgb("#f8fafc"),
    stroke: .75pt + muted,
    corner-radius: 3pt,
  ),

  flow((1.5, 0), (0, 1.5), label: [supported]),
  flow((0, 0), (1.5, 1.5), label: [repeatable]),
  flow((1.5, 0), (1.5, 1.5), label: [supported]),
  flow((0, 1.5), (0, 3), label: [admissible]),
  flow((0, 0), (0, 3), label: [repeatable], bend: -32deg),
  flow((0, 3), (0, 4.5), label: [learnable]),
  flow((0, 4.5), (1.5, 4.5), label: [recursive]),
  flow((1.5, 1.5), (1.5, 4.5), label: [meaningful]),
)
