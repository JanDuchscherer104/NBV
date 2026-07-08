#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9.4pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let actor = rgb("#2563eb")
#let belief = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let oracle = rgb("#dc2626")
#let loss = rgb("#b45309")

#let block(pos, title, body, tint: actor, width: 39mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.5pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(82%),
  stroke: .75pt + tint.darken(8%),
  corner-radius: 4pt,
)

#let lane(pos, body, tint: muted, width: 38mm) = node(
  pos,
  align(center)[#text(size: 7.1pt, weight: "bold", fill: tint.darken(10%))[#body]],
  width: width,
  fill: tint.lighten(90%),
  stroke: .55pt + tint.lighten(22%),
  corner-radius: 3pt,
)

#let warning(pos, body, width: 43mm) = node(
  pos,
  align(center)[#text(size: 7.0pt, fill: oracle.darken(15%))[#body]],
  width: width,
  fill: oracle.lighten(90%),
  stroke: .65pt + oracle.lighten(20%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (16mm, 12mm),
  edge-stroke: .84pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 74%,

  lane((0, 0), [V1 student actor path], tint: actor),
  block((0, 1.0), [Actor-visible state], [
    $bold(s)_t^"cf0"$, $bold(phi)_e$ \
    scene memory, history \
    $cal(Q)_t$, masks
  ], tint: actor, width: 42mm),
  block((0, 2.45), [Current-belief products], [
    optional belief render \
    or support/ray summaries \
    from actor memory only
  ], tint: belief, width: 42mm),
  block((0, 3.9), [Student value], [
    $Q_(H,theta)(bold(s)_t^"cf0", e, q_(t,i))$ \
    valid-row scores
  ], tint: model, width: 44mm),

  lane((2.75, 0), [Privileged teacher / oracle], tint: oracle),
  block((2.75, 1.0), [GT assets], [
    mesh, GT target crop \
    GT boxes for matching
  ], tint: oracle, width: 41mm),
  block((2.75, 2.45), [Dense candidate render], [
    depth, valid mask, \
    candidate points, target error
  ], tint: oracle, width: 43mm),
  block((2.75, 3.9), [Oracle values], [
    $r_t^e$, $G_t^((H))$ \
    upper bounds or teacher targets
  ], tint: loss, width: 43mm),

  lane((5.35, 0), [Training-only signals], tint: loss, width: 40mm),
  block((5.35, 1.15), [Return / ranking loss], [
    Monte-Carlo or TD target \
    masked over $m_(t,i)=1$
  ], tint: loss, width: 42mm),
  block((5.35, 2.65), [Optional distillation], [
    stop-gradient teacher value \
    ablation, not actor input
  ], tint: loss, width: 42mm),
  warning((5.35, 4.05), [
    forbidden at V1 inference: \
    GT depth, GT crop, or dense \
    candidate render as actor features
  ], width: 45mm),

  edge((0, 1.0), (0, 2.45), "-|>"),
  edge((0, 2.45), (0, 3.9), "-|>"),
  edge((2.75, 1.0), (2.75, 2.45), "-|>"),
  edge((2.75, 2.45), (2.75, 3.9), "-|>"),
  edge((2.75, 3.9), (5.35, 1.15), "-|>"),
  edge((0, 3.9), (5.35, 1.15), "-|>"),
  edge((2.75, 3.9), (5.35, 2.65), "--|>"),
  edge((0, 3.9), (5.35, 2.65), "-|>"),
  edge((2.75, 2.45), (5.35, 4.05), "--|>"),
)
