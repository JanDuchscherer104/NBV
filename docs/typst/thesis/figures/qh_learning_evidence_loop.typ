#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 9.4pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let factual = rgb("#16a34a")
#let state = rgb("#2563eb")
#let planned = rgb("#7c3aed")
#let model = rgb("#0f766e")

#let block(pos, title, body, tint: factual, width: 37mm) = node(
  pos,
  align(center)[
    #text(weight: "bold", size: 8.2pt)[#title] \
    #text(size: 7.0pt, fill: ink)[#body]
  ],
  width: width,
  inset: 5pt,
  fill: white,
  stroke: .82pt + tint,
  corner-radius: 3pt,
)

#let heading(pos, title, subtitle, tint: factual, width: 75mm) = node(
  pos,
  align(left)[
    #text(weight: "bold", size: 9pt, fill: tint.darken(8%))[#title] \
    #text(size: 6.9pt, fill: muted)[#subtitle]
  ],
  width: width,
  inset: 5pt,
  fill: tint.lighten(94%),
  stroke: .65pt + tint,
)

#let flow(from, to, label: none, tint: muted, dash: none) = edge(
  from,
  to,
  "-|>",
  label: if label == none { none } else { text(size: 6.8pt, fill: tint.darken(8%))[#label] },
  label-fill: white,
  stroke: .88pt + tint,
  dash: dash,
)

#diagram(
  spacing: 8pt,
  cell-size: (34mm, 14mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 4pt,
  mark-scale: 72%,

  heading((1.5, 0), [A. Factual selected-transition lineage], [
    persisted replay evidence; solid arrows are implemented joins
  ], tint: factual, width: 122mm),
  block((0, 1.25), [Current state], [
    $s_t$, full table $cal(Q)_t$ \
    action and train masks
  ], tint: state, width: 39mm),
  block((1.5, 1.25), [Selected valid action], [
    $a_t in cal(A)_t$ \
    one factual successor
  ], width: 39mm),
  block((3.0, 1.25), [Transition fields], [
    $r_t$, $d_t$, $gamma_t$ \
    successor step id
  ], width: 39mm),
  block((3.0, 2.8), [Successor state], [
    $s_(t+1)$, full $cal(Q)_(t+1)$ \
    mask $bold(m)_(t+1)$
  ], tint: state, width: 39mm),
  block((.7, 2.75), [One-step labels], [
    each candidate with $m_(t,i)^"train"=1$ \
    may carry oracle $r_t(i)$
  ], width: 42mm),

  heading((1.5, 4.35), [B. Implemented masked Double-Q computation], [
    selected estimator; scientific value evidence remains pending
  ], tint: model, width: 122mm),
  block((0, 5.7), [Valid successor rows], [
    restrict to $m_(t+1,j)=1$ \
    empty set terminates
  ], tint: model, width: 39mm),
  block((1.5, 5.7), [Online selection], [
    $a^star = arg max_j Q_theta$ \
    over valid rows only
  ], tint: model, width: 39mm),
  block((3.0, 5.7), [Target gather], [
    $Q_(bar(theta))(s_(t+1),a^star)$ \
    frozen target network
  ], tint: model, width: 39mm),
  block((3.0, 7.3), [Masked TD target], [
    $y_t=r_t+gamma_t(1-d_t)Q_(bar(theta))$ \
    no bootstrap through invalid rows
  ], tint: model, width: 45mm),
  block((0, 7.3), [Training admission], [
    $m_(t,a_t)^"train"=1$ \
    factual transition exists \
    successor link or terminal flag
  ], tint: model, width: 39mm),
  block((1.5, 7.3), [Loss contribution], [
    $(Q_theta(s_t,a_t)-y_t)^2$ \
    admitted rows only
  ], tint: model, width: 46mm),

  flow((0, 1.25), (1.5, 1.25), label: [choose]),
  flow((1.5, 1.25), (3.0, 1.25), label: [persist]),
  flow((3.0, 1.25), (3.0, 2.8), label: [resolve]),
  flow((0, 1.25), (.7, 2.75), label: [all eligible rows]),

  flow((0, 5.7), (1.5, 5.7), tint: model),
  flow((1.5, 5.7), (3.0, 5.7), tint: model),
  flow((3.0, 5.7), (3.0, 7.3), tint: model),
  flow((0, 7.3), (1.5, 7.3), tint: model),
  flow((3.0, 7.3), (1.5, 7.3), tint: model),
)
