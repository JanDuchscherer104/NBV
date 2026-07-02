#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 10pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let state = rgb("#2563eb")
#let candidate = rgb("#16a34a")
#let compute = rgb("#7c3aed")
#let output = rgb("#b45309")
#let oracle = rgb("#dc2626")

#let block(pos, title, body, tint: state, width: 38mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 8pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(78%),
  stroke: .8pt + tint.darken(10%),
  corner-radius: 4pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (20mm, 13mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 75%,

  block((0, 1), [Actor-visible context], [
    target token \
    scene/support memory \
    selected history + budget
  ], tint: state, width: 38mm),

  block((0, 2.8), [Candidate row $i$], [
    relative pose + relation \
    support pools \
    hard mask + reason
  ], tint: candidate, width: 38mm),

  block((2.3, 1.9), [Candidate-to-state query], [
    candidate row reads fixed \
    target, scene, history, budget
  ], tint: compute, width: 42mm),

  block((4.6, 1.9), [Residual value head], [
    $Q_H(s_t,e,q_(t,i))$ \
    $= hat(r)_psi^e + A_theta^H$
  ], tint: output, width: 39mm),

  block((6.55, 1.9), [Hard mask + selection], [
    invalid rows cannot score \
    $arg max_(i:m_(t,i)=1) Q_H$
  ], tint: output, width: 42mm),

  block((2.3, 3.55), [Optional set context], [
    DeepSets / masked attention \
    ablation, not default calibration
  ], tint: compute, width: 42mm),

  block((2.3, .05), [Oracle supervision only], [
    target RRI, TD targets, \
    endpoint gain, evaluation
  ], tint: oracle, width: 42mm),

  block((4.6, .05), [Training losses], [
    one-step calibration \
    finite-horizon residual
  ], tint: oracle, width: 36mm),

  edge((0, 1), (2.3, 1.9), "-|>"),
  edge((0, 2.8), (2.3, 1.9), "-|>"),
  edge((2.3, 1.9), (4.6, 1.9), "-|>"),
  edge((4.6, 1.9), (6.55, 1.9), "-|>"),
  edge((2.3, 3.55), (4.6, 1.9), "--|>"),
  edge((2.3, .05), (4.6, .05), "--|>"),
  edge((4.6, .05), (4.6, 1.9), "--|>"),
)
