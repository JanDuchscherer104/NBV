#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 10.2pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let state = rgb("#2563eb")
#let valid = rgb("#16a34a")
#let invalid = rgb("#dc2626")
#let beam = rgb("#7c3aed")
#let selected = rgb("#b45309")
#let oracle = rgb("#991b1b")

#let block(pos, title, body, tint: state, width: 32mm) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 7.8pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(82%),
  stroke: .75pt + tint.darken(8%),
  corner-radius: 4pt,
)

#let note(pos, body, tint: muted, width: 34mm) = node(
  pos,
  align(center)[#text(size: 7.0pt, fill: tint.darken(10%))[#body]],
  width: width,
  fill: tint.lighten(90%),
  stroke: .52pt + tint.lighten(28%),
  corner-radius: 3pt,
)

#let transition(from, to, action, tint: muted, dash: none, thickness: .85pt) = edge(
  from,
  to,
  "-|>",
  label: text(size: 7pt, fill: tint.darken(8%))[#action],
  label-fill: white,
  stroke: thickness + tint,
  dash: dash,
)

#diagram(
  spacing: 8pt,
  cell-size: (18mm, 13mm),
  edge-stroke: .82pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 72%,

  block((2.6, 0), [root state], [
    $s_t$, target $e$ \
    valid rows $cal(A)_t$
  ], tint: state, width: 32mm),

  block((0.55, 1.75), [successor state], [
    $s_(t+1)^((1))$ \
    regenerated table
  ], tint: valid, width: 34mm),
  block((2.6, 1.75), [successor state], [
    $s_(t+1)^((2))$ \
    regenerated table
  ], tint: selected, width: 34mm),
  block((4.65, 1.75), [legal, not retained], [
    $s_(t+1)^((3))$ \
    outside beam $B=2$
  ], tint: muted, width: 36mm),

  block((0.55, 3.55), [depth-$2$ leaf], [
    return $G_1^((2))$ \
    terminal or horizon
  ], tint: valid, width: 34mm),
  block((2.6, 3.55), [depth-$2$ leaf], [
    return $G_2^((2))$ \
    terminal or horizon
  ], tint: selected, width: 34mm),

  note((4.9, .25), [
    $q_(t,4): m_(t,4)=0$ \
    invalid row; no child
  ], tint: invalid, width: 35mm),
  note((4.85, 3.55), [
    constructed symbolic topology \
    no measured reward is implied
  ], tint: beam, width: 40mm),

  block((.55, 4.8), [one-step greedy], [
    $r_(t,1) > r_(t,2)$ \
    selects first action $q_(t,1)$
  ], tint: valid, width: 38mm),
  block((2.75, 4.8), [bounded lookahead], [
    $G_2^((2)) > G_1^((2))$ \
    selects first action $q_(t,2)$
  ], tint: selected, width: 42mm),

  transition((2.6, 0), (.55, 1.75), [$q_(t,1), r_(t,1)$], tint: valid),
  transition((2.6, 0), (2.6, 1.75), [$q_(t,2), r_(t,2)$], tint: selected, thickness: 1.35pt),
  transition((2.6, 0), (4.65, 1.75), [$q_(t,3), r_(t,3)$], dash: "dashed"),
  transition((.55, 1.75), (.55, 3.55), [$q'_(1), r'_(1)$], tint: valid),
  transition((2.6, 1.75), (2.6, 3.55), [$q'_(2), r'_(2)$], tint: selected, thickness: 1.35pt),
  edge((.55, 3.55), (.55, 4.8), "--|>", stroke: .7pt + valid),
  edge((2.6, 3.55), (2.75, 4.8), "-|>", stroke: 1.1pt + selected),
)
