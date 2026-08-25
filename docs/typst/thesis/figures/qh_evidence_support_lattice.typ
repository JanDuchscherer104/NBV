#import "@preview/fletcher:0.5.8": diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 8.7pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let raw = rgb("#475569")
#let action = rgb("#2563eb")
#let label = rgb("#16a34a")
#let successor = rgb("#b45309")
#let exact = rgb("#7c3aed")

#let stage(pos, title, body, mask, tint) = node(
  pos,
  align(left)[
    #text(weight: "bold", size: 8.4pt, fill: tint.darken(10%))[#title] \
    #text(size: 7pt, fill: ink)[#body]
  ],
  width: 90mm,
  inset: 5pt,
  fill: tint.lighten(93%),
  stroke: .8pt + tint,
  corner-radius: 3pt,
)

#let mask-box(pos, mask, meaning, tint) = node(
  pos,
  align(center)[
    #text(weight: "bold", size: 7pt, fill: tint.darken(10%))[#mask] \
    #text(size: 6.2pt, fill: muted)[#meaning]
  ],
  width: 38mm,
  inset: 4pt,
  fill: white,
  stroke: .65pt + tint,
  corner-radius: 3pt,
)

#let down(from, to, tint) = edge(
  from,
  to,
  "-|>",
  stroke: 1pt + tint,
)

#diagram(
  spacing: 7pt,
  cell-size: (44mm, 14mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 3pt,
  mark-scale: 70%,

  node(
    (1.0, 0),
    align(center)[
      #text(weight: "bold", size: 10pt, fill: ink)[Exact-$Q_h$ evidence-support lattice]
      #v(2pt)
      #text(size: 7pt, fill: muted)[Each restriction removes rows that cannot support the corresponding factual target. Dense one-step labels do not imply dense multi-step support.]
    ],
    width: 125mm,
    inset: 6pt,
    fill: rgb("#f1f5f9"),
    stroke: 1pt + raw,
    corner-radius: 3pt,
  ),

  stage((0, 1.35), [Materialized candidate rows], [all rows emitted by the candidate table; rows may be invalid or unlabeled], [candidate table], raw),
  mask-box((1.45, 1.35), [$bold(m)_t^"cand"$], [row exists], raw),

  stage((0, 2.75), [Hard-action support], [rows permitted by geometry and action feasibility; selection cannot use other rows], [candidate rows ∩ valid actions], action),
  mask-box((1.45, 2.75), [$bold(m)_t^"act"$], [hard validity], action),

  stage((0, 4.15), [One-step label support], [admitted rows carry a factual immediate target; dense labels can still lack transitions], [hard-action rows ∩ labels], label),
  mask-box((1.45, 4.15), [$bold(m)_t^(Q,1)$], [one-step label], label),

  stage((0, 5.55), [Selected factual transition], [the selected row has a resolved successor state or an explicit terminal outcome], [label rows ∩ selected transition], successor),
  mask-box((1.45, 5.55), [$m_t^"succ"$], [successor link], successor),

  stage((0, 6.95), [Exact-$Q_2$ certification], [nonterminal rows require an admitted exact successor label; terminal rows have zero continuation], [supported successor or terminal], exact),
  mask-box((1.45, 6.95), [$(d_t=1) or (m_t^"succ" and m_(t+1,j)^(Q,1))$], [exact target], exact),

  node(
    (0, 8.35),
    align(left)[
      #text(weight: "bold", size: 8.3pt, fill: exact.darken(10%))[Longer horizons require recursive support]
      #v(2pt)
      #text(size: 7pt, fill: ink)[For $h > 2$, each nonterminal backup recurses through supported evidence at horizon $h-1$; terminal continuation remains exactly zero.]
    ],
    width: 90mm,
    inset: 5pt,
    fill: exact.lighten(93%),
    stroke: .8pt + exact,
    corner-radius: 3pt,
  ),
  mask-box((1.45, 8.35), [$(d_t=1) or (m_t^"succ" and m_(t+1,j)^(Q,h-1))$], [recursive support], exact),

  down((0, 1.35), (0, 2.75), action),
  down((0, 2.75), (0, 4.15), label),
  down((0, 4.15), (0, 5.55), successor),
  down((0, 5.55), (0, 6.95), exact),
  down((0, 6.95), (0, 8.35), exact),
  edge((1.45, 1.35), (1.45, 2.75), "-|>", stroke: .65pt + muted, dash: "dashed"),
  edge((1.45, 2.75), (1.45, 4.15), "-|>", stroke: .65pt + muted, dash: "dashed"),
  edge((1.45, 4.15), (1.45, 5.55), "-|>", stroke: .65pt + muted, dash: "dashed"),
  edge((1.45, 5.55), (1.45, 6.95), "-|>", stroke: .65pt + muted, dash: "dashed"),
  edge((1.45, 6.95), (1.45, 8.35), "-|>", stroke: .65pt + muted, dash: "dashed"),
)
