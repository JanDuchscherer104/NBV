#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: 160mm, height: auto, margin: 0mm, fill: white)
#set text(font: "New Computer Modern", size: 9.2pt, fill: rgb("#18212b"))

#let ink = rgb("#18212b")
#let muted = rgb("#5d6977")
#let source = rgb("#2867a7")
#let factual = rgb("#23835f")
#let derived = rgb("#7451a6")
#let selected = rgb("#a85b16")

#let table-node(pos, title, key, body, tint: factual, width: 24mm, name: none) = node(
  pos,
  align(left)[
    #align(center, text(weight: "bold", size: 8.8pt)[#title])
    #line(length: 100%, stroke: .45pt + tint.lighten(30%))
    #text(size: 7.7pt, weight: "bold", fill: ink)[#key] \
    #text(size: 7.45pt, fill: ink)[#body]
  ],
  name: name,
  width: width,
  inset: 5.5pt,
  fill: tint.lighten(89%),
  stroke: .78pt + tint.darken(5%),
  corner-radius: 3pt,
)

#let cardinality(from, to) = edge(
  from,
  to,
  "-|>",
  label: text(size: 7pt, fill: muted)[1:n],
  label-fill: white,
  stroke: .9pt + muted,
)

#grid(
  columns: (26mm, 1fr),
  column-gutter: 4mm,
  align(center, text(size: 7.9pt, weight: "bold", fill: source)[Immutable source store]),
  align(center, [
    #text(size: 8.2pt, weight: "bold", fill: factual)[Factual replay tables]
    #h(1.2mm)
    #text(size: 7.5pt, fill: muted)[retained evidence, not an exhaustive tree]
  ]),
)
#v(1.2mm)

#align(center, diagram(
  spacing: 6mm,
  cell-size: 0pt,
  edge-stroke: .9pt + muted,
  edge-corner-radius: 4pt,
  mark-scale: 75%,

  table-node((0, 1), [Source row], [`source_row_id`], [
    VIN actor/oracle substrate \
    manifest identity
  ], tint: source, width: 26mm, name: <source>),
  table-node((1, 0), [Target task], [`target_row_id`], [
    `target_id` \
    task and validity
  ], name: <target>),
  table-node((1, 1), [Retained chain], [`rollout_row_id`], [
    source + target row IDs \
    policy, recipe, lineage
  ], name: <rollout>),
  table-node((2, 1), [Ordered step], [`step_row_id`], [
    `rollout_row_id`, $t$ \
    selected candidate ID
  ], width: 26mm, name: <step>),
  table-node((3, 1), [Full candidate shell], [`candidate_row_id`], [
    `step_row_id`, shell $i$ \
    #text(fill: selected, weight: "bold")[●] exactly one selected row
  ], width: 28mm, name: <candidate>),

  node(
    enclose: (<target>, <rollout>, <step>, <candidate>),
    inset: 5pt,
    outset: 2pt,
    fill: none,
    stroke: (paint: factual, thickness: .7pt, dash: "dashed"),
    corner-radius: 5pt,
    snap: -1,
  ),

  cardinality(<source>, <rollout>),
  cardinality(<target>, <rollout>),
  cardinality(<rollout>, <step>),
  cardinality(<step>, <candidate>),
))

#v(1.6mm)
#align(center)[
  #text(size: 7.7pt, fill: derived)[materialize: join IDs $arrow.r$ copy/validate masks $arrow.r$ pad]
  #linebreak()
  #text(size: 13pt, fill: derived)[$arrow.b$]
]
#v(.5mm)

#align(center, block(
  width: 110mm,
  inset: (x: 3mm, y: 2mm),
  fill: derived.lighten(91%),
  stroke: (paint: derived, thickness: .85pt, dash: "dashed"),
  radius: 2mm,
  [
    #align(center, text(weight: "bold", size: 9pt, fill: derived)[Derived $Q_H$ training cache])
    #line(length: 100%, stroke: .5pt + derived.lighten(28%))
    #grid(
      columns: (1fr, 1.45fr),
      column-gutter: 4mm,
      row-gutter: 1.2mm,
      text(size: 7.7pt, weight: "bold")[`q_h/[T,N_q]`],
      text(size: 7.6pt)[IDs + action/training masks + rewards],
      text(size: 7.6pt)[selected-action TD successor],
      text(size: 7.6pt)[validated against factual source tables],
    )
  ],
))

#v(1.7mm)
#block(
  width: 100%,
  inset: (x: 2.6mm, y: 1.6mm),
  fill: rgb("#f5f7f9"),
  stroke: (left: 1.3pt + selected),
  [
    #text(size: 8.1pt, weight: "bold")[Scientific boundary.]
    #h(1mm)
    #text(size: 7.9pt)[Solid links preserve factual row references; #text(fill: selected, weight: "bold")[●] marks the selected candidate. The dashed $Q_H$ cache is a verified projection of those rows, not an independent transition table.]
  ],
)
