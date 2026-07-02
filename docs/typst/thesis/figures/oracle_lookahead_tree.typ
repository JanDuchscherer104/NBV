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

#let row(pos, title, body, tint: valid, width: 30mm) = node(
  pos,
  align(center)[
    #text(size: 7.8pt, weight: "bold")[#title] \
    #text(size: 7.2pt, fill: ink)[#body]
  ],
  width: width,
  fill: tint.lighten(84%),
  stroke: .7pt + tint.darken(8%),
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

#diagram(
  spacing: 8pt,
  cell-size: (18mm, 13mm),
  edge-stroke: .82pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 72%,

  block((2.6, 0), [root state], [
    $s_t$, target $e$ \
    finite table $cal(Q)_t$
  ], tint: state, width: 32mm),

  row((0, 1.35), [$q_(t,1)$], [
    $m=1$, $r_0=0.32$ \
    myopic winner
  ], tint: valid),
  row((1.75, 1.35), [$q_(t,2)$], [
    $m=1$, $r_0=0.24$ \
    opens target side
  ], tint: selected),
  row((3.5, 1.35), [$q_(t,3)$], [
    $m=1$, $r_0=0.13$ \
    lower prefix
  ], tint: valid),
  row((5.25, 1.35), [$q_(t,4)$], [
    $m=0$, $rho="path"$ \
    hard mask
  ], tint: invalid),

  note((2.6, 2.35), [
    beam $B=2$ retains \
    valid prefixes $q_1,q_2$
  ], tint: beam, width: 40mm),

  row((0.9, 3.35), [$q_1 -> q'_a$], [
    continuation $+0.03$ \
    $G^((2))=0.35$
  ], tint: valid, width: 32mm),
  row((2.9, 3.35), [$q_2 -> q'_b$], [
    continuation $+0.23$ \
    $G^((2))=0.47$
  ], tint: selected, width: 32mm),
  row((4.9, 3.35), [not expanded], [
    valid row outside \
    retained beam
  ], tint: muted, width: 32mm),

  block((1.65, 4.75), [greedy label], [
    one-step would \
    choose $a_t=1$
  ], tint: valid, width: 30mm),
  block((3.55, 4.75), [lookahead label], [
    best chain selects \
    first action $a_t=2$
  ], tint: selected, width: 36mm),
  note((5.35, 4.75), [
    invalid rows get \
    no branch and no \
    return target
  ], tint: oracle, width: 32mm),

  edge((2.6, 0), (0, 1.35), "-|>"),
  edge((2.6, 0), (1.75, 1.35), "-|>"),
  edge((2.6, 0), (3.5, 1.35), "-|>"),
  edge((2.6, 0), (5.25, 1.35), "--|>"),
  edge((0, 1.35), (2.6, 2.35), "-|>"),
  edge((1.75, 1.35), (2.6, 2.35), "-|>"),
  edge((2.6, 2.35), (0.9, 3.35), "-|>"),
  edge((2.6, 2.35), (2.9, 3.35), "-|>"),
  edge((3.5, 1.35), (4.9, 3.35), "--|>"),
  edge((5.25, 1.35), (5.35, 4.75), "--|>"),
  edge((0.9, 3.35), (1.65, 4.75), "--|>"),
  edge((2.9, 3.35), (3.55, 4.75), "-|>"),
  edge((0.9, 3.35), (3.55, 4.75), "--|>"),
)
