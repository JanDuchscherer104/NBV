#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9.2pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let state = rgb("#2563eb")
#let oracle = rgb("#dc2626")
#let store = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let eval = rgb("#b45309")

#let block(pos, title, body, tint: state, width: 42mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.2pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(80%),
  stroke: .75pt + tint.darken(10%),
  corner-radius: 4pt,
)

#let label(pos, body, tint: muted, width: 42mm) = node(
  pos,
  align(center)[#text(size: 7.0pt, fill: tint.darken(10%))[#body]],
  width: width,
  fill: tint.lighten(88%),
  stroke: .55pt + tint.lighten(25%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (24mm, 11mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 75%,

  label((0, 0), [A. Rollout materialization], tint: state),
  block((0, 1.0), [State and table], [
    $bold(s)_t$, $cal(Q)_t$ \
    masks and reasons
  ], tint: store),
  block((0, 2.1), [Oracle score], [
    target RRI for \
    every valid row
  ], tint: oracle),
  block((0, 3.2), [Select and step], [
    choose valid $a_t$ \
    fuse selected geometry \
    regenerate $cal(Q)_(t+1)$
  ], tint: eval),
  block((0, 4.3), [Replay row], [
    row labels plus \
    selected lineage
  ], tint: store),

  label((2.35, 0), [B. Masked Double-Q target], tint: model),
  block((2.35, 1.0), [Replay sample], [
    $bold(s), cal(Q), bold(m)$ \
    $bold(s)', cal(Q)', bold(m)'$
  ], tint: store),
  block((2.35, 2.1), [Online selector], [
    $i^* = arg max_(j:m'j=1)$ \
    $Q_theta(bold(s)', q'_j)$
  ], tint: model),
  block((2.35, 3.2), [Target backup], [
    $Q_bar(theta)(bold(s)', q'_(i^*))$ \
    $y = r^e + gamma Q_bar(theta)(.)$ \
    masked loss
  ], tint: eval, width: 38mm),
  block((2.35, 4.3), [Held-out policy], [
    deploy $pi_Q$ \
    oracle-rescore trajectory
  ], tint: oracle),

  label((1.18, 5.35), [All valid rows can receive one-step labels; only the selected row creates successor observations.], tint: oracle, width: 82mm),

  edge((0, 1.0), (0, 2.1), "--|>"),
  edge((0, 1.0), (0, 3.2), "-|>"),
  edge((0, 2.1), (0, 4.3), "--|>"),
  edge((0, 3.2), (0, 4.3), "-|>"),
  edge((0, 4.3), (2.35, 1.0), "-|>"),
  edge((2.35, 1.0), (2.35, 2.1), "-|>"),
  edge((2.35, 2.1), (2.35, 3.2), "-|>"),
  edge((2.35, 3.2), (2.35, 4.3), "--|>"),
)
