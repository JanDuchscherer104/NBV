#import "@preview/fletcher:0.5.8" as fletcher: diagram, edge, node

#set page(width: auto, height: auto, margin: 4mm, fill: white)
#set text(font: "New Computer Modern", size: 10pt)

#let ink = rgb("#1f2937")
#let muted = rgb("#64748b")
#let actor = rgb("#2563eb")
#let memory = rgb("#16a34a")
#let model = rgb("#7c3aed")
#let oracle = rgb("#dc2626")
#let label = rgb("#b45309")

#let block(pos, title, body, tint: actor, width: 37mm, name: none) = node(
  pos,
  align(center)[
    #text(weight: "bold")[#title] \
    #text(size: 9pt, fill: ink)[#body]
  ],
  name: name,
  width: width,
  fill: tint.lighten(80%),
  stroke: .75pt + tint.darken(10%),
  corner-radius: 4pt,
)

#let note(pos, body, tint: muted, width: 35mm, name: none) = node(
  pos,
  align(center)[#text(size: 8pt, fill: ink)[#body]],
  name: name,
  width: width,
  fill: tint.lighten(88%),
  stroke: .65pt + tint.darken(10%),
  corner-radius: 3pt,
)

#diagram(
  spacing: 8pt,
  cell-size: (17mm, 11.5mm),
  edge-stroke: .85pt + muted,
  edge-corner-radius: 5pt,
  mark-scale: 75%,

  note((1.2, 0), [Decision-time forward pass: provenance-explicit inputs], tint: model, width: 80mm),
  block((0, 1.15), [Logged evidence], [
    RGB, pose, calibration \
    semi-dense or fused geometry \
    frozen EVL features / support \
    observed target source ($"v1"$)
  ], tint: actor, width: 40mm, name: <logged>),
  block((2.4, 1.15), [Model state and target], [
    $s_t^"cf0"$, admitted descriptor $bold(phi)_e$ \
    selected-view history \
    remaining budget; source named
  ], tint: memory, width: 41mm, name: <state>),
  block((0, 2.95), [Candidate rows], [
    finite poses $cal(Q)_t$ \
    protocol-legal row features \
    proposal provenance explicit
  ], tint: actor, width: 40mm, name: <candidates>),
  block((2.4, 2.95), [$Q_H$ candidate scorer], [
    $f_theta$ on $(s_t, e, q_(t,i), h)$ \
    raw value and feasibility logit \
    per materialized row
  ], tint: model, width: 39mm, name: <scorer>),
  block((2.4, 4.65), [Predictions and action], [
    raw $Q_(h,theta,e,i)^"cond"$ and feasibility \
    masked selection downstream
  ], tint: model, width: 35mm, name: <prediction>),
  block((0, 4.65), [Hard action support], [
    $m_(t,i)^"act"$ \
    gates selection; feasibility target \
    never changes raw $Q_H$
  ], tint: actor, width: 40mm, name: <mask>),
  note((0, 6.4), [Reason codes explain rejected rows; they are neither embeddings nor low rewards.], tint: muted, width: 42mm, name: <audit>),

  note((4.9, 0), [Privileged offline / control sources], tint: oracle, width: 40mm),
  block((4.9, 1.15), [Privileged scene assets], [
    mesh, GT boxes, target crop \
    identity and evaluation support \
    GT descriptor source ($"v0"$)
  ], tint: oracle, width: 42mm, name: <assets>),
  block((4.9, 2.95), [Candidate renders], [
    hard-valid candidate depth / points \
    target endpoint error
  ], tint: oracle, width: 42mm, name: <renders>),
  block((4.9, 4.75), [Oracle targets], [
    one-step target RRI \
    bounded returns and upper bounds
  ], tint: label, width: 42mm, name: <targets>),
  block((4.9, 6.4), [$Q$-label support], [
    $m_(t,i)^(Q,h) <= m_(t,i)^"act"$ \
    finite value-target rows \
    gates value loss and successor backup
  ], tint: label, width: 42mm, name: <label-support>),

  block((2.4, 6.4), [Training / evaluation only], [
    prediction--target comparison \
    value / feasibility loss, metrics \
    named ablations
  ], tint: label, width: 43mm, name: <comparison>),

  edge(
    <logged>,
    <state>,
    "-|>",
    stroke: .9pt + actor,
    label: text(size: 7.2pt, fill: actor)[$"v1"$: observed],
    label-pos: 0.58,
  ),
  edge(
    <assets>,
    <state>,
    "--|>",
    stroke: .75pt + oracle,
    label: text(size: 7.2pt, fill: oracle)[$"v0"$: GT control],
    label-pos: 0.46,
  ),
  edge(<state>, <scorer>, "-|>", stroke: .9pt + memory),
  edge(<candidates>, <scorer>, "-|>", stroke: .9pt + actor),
  edge(<scorer>, <prediction>, "-|>", stroke: .9pt + model),
  edge(<mask>, <prediction>, "-|>", stroke: .9pt + actor),
  edge(<mask>, <audit>, "--|>", stroke: .65pt + muted),
  edge(
    <mask>,
    (1.2, 4.65),
    (1.2, 6.4),
    <comparison>,
    "--|>",
    stroke: .7pt + actor,
    label: text(size: 7.2pt, fill: actor)[feasibility target],
    label-pos: 0.72,
  ),

  edge(<assets>, <renders>, "-|>", stroke: .9pt + oracle),
  edge(<renders>, <targets>, "-|>", stroke: .9pt + oracle),
  edge(<prediction>, <comparison>, "-|>", stroke: .85pt + model),
  edge(<targets>, <label-support>, "-|>", stroke: .85pt + oracle),
  edge(
    <label-support>,
    <comparison>,
    "--|>",
    stroke: .85pt + oracle,
    label: text(size: 7.4pt, fill: oracle)[value supervision],
    label-pos: 0.48,
  ),
)
