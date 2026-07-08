#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9.5pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let actor = rgb("#2563eb")
#let memory = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let oracle = rgb("#dc2626")
#let label = rgb("#b45309")

#let block(pos, title, body, tint: actor, width: 39mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.8pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(80%),
  stroke: .75pt + tint.darken(10%),
  corner-radius: 4pt,
)

#let note(pos, body, tint: muted, width: 31mm) = node(
  pos,
  align(center)[#text(size: 7.2pt, fill: tint.darken(10%))[#body]],
  width: width,
  fill: tint.lighten(88%),
  stroke: .55pt + tint.lighten(25%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (19mm, 13mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 75%,

  note((0, 0), [Actor-visible evidence], tint: actor, width: 35mm),
  block((0, 1.0), [Logged state], [
    RGB/pose/calibration \
    semidense or fused geometry
  ], tint: actor),
  block((0, 2.35), [Target and scene tokens], [
    frozen EVL support \
    target descriptor $bold(phi)_e$ \
    history, budget, masks
  ], tint: memory),
  block((0, 3.7), [Candidate table], [
    finite poses $cal(Q)_t$ \
    row features, validity, reason
  ], tint: actor),

  note((2.6, 0), [Legal actor interface], tint: model, width: 38mm),
  block((2.6, 1.45), [Counterfactual actor state], [
    $bold(s)_t^"cf0"$ \
    no hidden target labels \
    no future visual features
  ], tint: model, width: 43mm),
  block((2.6, 3.0), [$Q_H$ candidate scorer], [
    scores only valid rows \
    argmax / loss respects mask
  ], tint: model, width: 40mm),

  note((5.25, 0), [Oracle-only products], tint: oracle, width: 36mm),
  block((5.25, 1.0), [GT scene assets], [
    mesh, GT boxes, target crop \
    identity match and label support
  ], tint: oracle, width: 41mm),
  block((5.25, 2.35), [Candidate renders], [
    privileged depth / point sets \
    target-specific reconstruction error
  ], tint: oracle, width: 41mm),
  block((5.25, 3.7), [Labels and evaluation], [
    target RRI, returns, upper bounds \
    teacher ablations if named
  ], tint: label, width: 41mm),

  note((2.6, 4.55), [Hard boundary: oracle products supervise training and evaluation, not actor inputs], tint: oracle, width: 52mm),

  edge((0, 1.0), (2.6, 1.45), "-|>"),
  edge((0, 2.35), (2.6, 1.45), "-|>"),
  edge((0, 3.7), (2.6, 1.45), "-|>"),
  edge((2.6, 1.45), (2.6, 3.0), "-|>"),
  edge((5.25, 1.0), (5.25, 2.35), "-|>"),
  edge((5.25, 2.35), (5.25, 3.7), "-|>"),
  edge((5.25, 3.7), (2.6, 4.55), "--|>"),
  edge((2.6, 4.55), (2.6, 3.0), "--|>"),
)
