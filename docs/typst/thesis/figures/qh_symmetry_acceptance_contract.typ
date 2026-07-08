#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let state = rgb("#2563eb")
#let geometry = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let mask = rgb("#b45309")
#let oracle = rgb("#dc2626")

#let block(pos, title, body, tint: state, width: 42mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.2pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(80%),
  stroke: .7pt + tint.darken(8%),
  corner-radius: 4pt,
)

#let note(pos, body, tint: muted, width: 38mm) = node(
  pos,
  align(center)[#text(size: 7pt, fill: tint.darken(12%))[#body]],
  width: width,
  fill: tint.lighten(90%),
  stroke: .55pt + tint.lighten(25%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (24mm, 12mm),
  edge-stroke: .78pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 72%,

  note((0, 0), [Actor-visible inputs], tint: state),
  block((0, 1.0), [State and target], [
    scene memory, target token \
    selected history, budget
  ], tint: state),
  block((0, 2.35), [Candidate rows], [
    $x_(t,i)$, $m_(t,i)$, reason code \
    unordered finite action table
  ], tint: state),
  block((0, 3.7), [Oracle products], [
    GT mesh, target RRI, TD target \
    supervise loss/evaluation only
  ], tint: oracle, width: 44mm),

  note((2.35, 0), [Descriptor / model contract], tint: model, width: 44mm),
  block((2.35, 1.0), [Local-frame geometry], [
    root/current reference pose \
    candidate-local target relation
  ], tint: geometry, width: 44mm),
  block((2.35, 2.35), [Directional history], [
    target-local $bb(S)^2$ memory \
    separate from pose features
  ], tint: geometry, width: 44mm),
  block((2.35, 3.7), [Mask-safe scorer], [
    row-wise baseline first \
    set context only as ablation
  ], tint: model, width: 44mm),

  note((4.7, 0), [Acceptance tests], tint: mask),
  block((4.7, 1.0), [Row permutation], [
    $f_theta(Pi X_t,m_t)$ \
    $= Pi f_theta(X_t,m_t)$
  ], tint: mask),
  block((4.7, 2.35), [Mask isolation], [
    invalid/padded rows blocked \
    except explicit count features
  ], tint: mask),
  block((4.7, 3.7), [Actor provenance gate], [
    actor graph scores valid rows \
    no hidden labels or GT crops
  ], tint: geometry, width: 44mm),

  edge((0, 1.0), (2.35, 1.0), "-|>"),
  edge((0, 2.35), (2.35, 1.0), "-|>"),
  edge((0, 1.0), (2.35, 2.35), "-|>"),
  edge((2.35, 1.0), (2.35, 3.7), "-|>"),
  edge((2.35, 2.35), (2.35, 3.7), "-|>"),
  edge((2.35, 3.7), (4.7, 1.0), "-|>"),
  edge((0, 2.35), (4.7, 1.0), "--|>"),
  edge((0, 2.35), (4.7, 2.35), "--|>"),
  edge((2.35, 3.7), (4.7, 2.35), "-|>"),
  edge((0, 3.7), (4.7, 3.7), "--|>"),
  edge((4.7, 1.0), (4.7, 3.7), "-|>"),
  edge((4.7, 2.35), (4.7, 3.7), "-|>"),
)
