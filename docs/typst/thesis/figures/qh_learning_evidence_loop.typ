#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let source = rgb("#2563eb")
#let oracle = rgb("#dc2626")
#let replay = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let eval = rgb("#b45309")

#let block(pos, title, body, tint: source, width: 42mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.1pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(80%),
  stroke: .72pt + tint.darken(8%),
  corner-radius: 4pt,
)

#let note(pos, body, tint: muted, width: 40mm) = node(
  pos,
  align(center)[#text(size: 7pt, fill: tint.darken(12%))[#body]],
  width: width,
  fill: tint.lighten(90%),
  stroke: .55pt + tint.lighten(25%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (24mm, 11.2mm),
  edge-stroke: .82pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 72%,

  note((0, 0), [One-step evidence], tint: oracle),
  block((0, 1.05), [Root state and target], [
    actor-visible state \
    finite candidate table
  ], tint: source),
  block((0, 2.35), [All-valid oracle labels], [
    target RRI $r_t^e(i)$ \
    ranking and calibration gate
  ], tint: oracle, width: 44mm),
  block((0, 3.65), [Myopic scorer accepted], [
    top-$k$, calibration, support \
    before #text(style: "italic")[Q]#text(size: 6pt)[H] interpretation
  ], tint: eval, width: 44mm),

  note((2.25, 0), [Selected-transition replay], tint: replay, width: 43mm),
  block((2.25, 1.05), [Rollout policy], [
    random-valid, greedy, \
    lookahead, or softmax
  ], tint: replay, width: 43mm),
  block((2.25, 2.35), [Materialized successor], [
    selected depth/geometry \
    regenerated next table + mask
  ], tint: replay, width: 45mm),
  block((2.25, 3.65), [Replay row], [
    state, action, reward, \
    next state, terminal flag
  ], tint: replay, width: 43mm),

  note((4.5, 0), [Learning and evaluation], tint: model, width: 43mm),
  block((4.5, .9), [Masked Double-Q], [
    online argmax over valid \
    target backup for $y_t$
  ], tint: model, width: 43mm),
  block((4.5, 2.0), [Residual value model], [
    one-step scorer plus \
    finite-horizon residual
  ], tint: model, width: 43mm),
  block((4.5, 3.1), [Held-out policy], [
    select valid action chains \
    with fixed masks/seeds
  ], tint: model, width: 43mm),
  block((4.5, 4.2), [Oracle re-score], [
    endpoint target gain \
    return, invalidity, cost
  ], tint: oracle, width: 43mm),
  block((4.5, 5.3), [Reportable comparison], [
    paired roots and targets \
    headroom, wins, failures
  ], tint: eval, width: 43mm),

  note((1.12, 5.3), [All valid candidates may train one-step labels; only selected actions create successor evidence for bootstrapped #text(style: "italic")[Q]#text(size: 6pt)[H].], tint: oracle, width: 78mm),

  edge((0, 1.05), (0, 2.35), "-|>"),
  edge((0, 2.35), (0, 3.65), "-|>"),
  edge((0, 3.65), (2.25, 1.05), "-|>"),
  edge((2.25, 1.05), (2.25, 2.35), "-|>"),
  edge((2.25, 2.35), (2.25, 3.65), "-|>"),
  edge((2.25, 3.65), (4.5, .9), "-|>"),
  edge((4.5, .9), (4.5, 2.0), "-|>"),
  edge((4.5, 2.0), (4.5, 3.1), "-|>"),
  edge((4.5, 3.1), (4.5, 4.2), "-|>"),
  edge((4.5, 4.2), (4.5, 5.3), "-|>"),
  edge((0, 2.35), (4.5, 2.0), "--|>"),
  edge((2.25, 2.35), (4.5, .9), "--|>"),
)
