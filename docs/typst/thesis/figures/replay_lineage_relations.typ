#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let source = rgb("#2563eb")
#let fact = rgb("#16a34a")
#let derived = rgb("#7c3aed")
#let selected = rgb("#b45309")

#let entity(pos, title, key, body, tint: fact, width: 35mm) = node(
  pos,
  align(left)[
    #align(center, text(weight: "bold", size: 8.2pt)[#title])
    #line(length: 100%, stroke: .45pt + tint.lighten(35%))
    #text(size: 7.1pt, weight: "bold", fill: ink)[#key] \
    #text(size: 6.95pt, fill: ink)[#body]
  ],
  width: width,
  inset: 5pt,
  fill: tint.lighten(88%),
  stroke: .72pt + tint.darken(5%),
  corner-radius: 3pt,
)

#let relation(from, to, cardinality, dash: none, tint: muted, bend: 0deg) = edge(
  from,
  to,
  "-|>",
  label: if cardinality == none { none } else { text(size: 6.6pt, fill: muted)[#cardinality] },
  label-fill: white,
  stroke: .82pt + tint,
  dash: dash,
  bend: bend,
)

#diagram(
  spacing: 7pt,
  cell-size: (35mm, 20mm),
  edge-stroke: .82pt + muted,
  edge-corner-radius: 4pt,
  mark-scale: 72%,

  entity((0, 0), [VIN source row], [`sample_index`], [
    immutable logged state \
    cached actor/oracle substrate
  ], tint: source),
  entity((1.45, 0), [Target], [`target_row_id`], [
    `source_row_id` \
    oracle task and validity
  ]),
  entity((2.9, 0), [Retained rollout], [`rollout_row_id`], [
    `target_row_id` \
    policy, recipe, chain
  ]),
  entity((.5, 1.7), [Step], [`step_row_id`], [
    `rollout_row_id`, $t$ \
    selected action link
  ]),
  entity((1.95, 1.7), [Candidate row], [`candidate_row_id`], [
    `step_row_id`, shell $i$ \
    pose, mask, reward
  ]),

  entity((1.95, 3.45), [Derived $Q_H$ training view], [`q_h/[T,N_q]`], [
    padded cache; selected-action successor and TD fields are derived from factual rows
  ], tint: derived, width: 76mm),

  relation((0, 0), (1.45, 0), [1 : many]),
  relation((1.45, 0), (2.9, 0), [1 : many]),
  relation((2.9, 0), (.5, 1.7), [1 : many]),
  relation((.5, 1.7), (1.95, 1.7), [1 : full shell]),
  relation(
    (.5, 1.7),
    (1.95, 1.7),
    [`selected_candidate_row_id`: 0 or 1],
    tint: selected,
    bend: 28deg,
  ),
  relation((1.45, 0), (1.95, 3.45), none, dash: "dashed"),
  relation((2.9, 0), (1.95, 3.45), none, dash: "dashed"),
  relation((.5, 1.7), (1.95, 3.45), none, dash: "dashed"),
  relation((1.95, 1.7), (1.95, 3.45), none, dash: "dashed"),
)
