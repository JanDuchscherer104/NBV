// Proposal-local visual helpers. These use Typst built-ins so the proposal
// remains portable even when Typst Universe packages are unavailable.

#let proposal-red = rgb("#fc5555")
#let proposal-blue = rgb("#003B70")
#let proposal-ink = rgb("#222A35")
#let proposal-muted = rgb("#5F6670")
#let proposal-paper = rgb("#F6F8FA")
#let proposal-rule = rgb("#D6DEE8")

#let proposal-style(body) = {
  set math.equation(numbering: "(1)")
  show heading.where(level: 1): set block(above: 1.9em, below: 0.8em)
  show heading.where(level: 1): set text(size: 16pt, weight: 700, fill: proposal-blue)
  show heading.where(level: 2): set block(above: 1.25em, below: 0.55em)
  show heading.where(level: 2): set text(size: 12.5pt, weight: 600, fill: proposal-red)
  show figure.caption: set text(size: 9.5pt, fill: proposal-muted)
  show raw.where(block: false): box.with(
    fill: proposal-paper,
    inset: (x: 3pt, y: 0pt),
    outset: (y: 2pt),
    radius: 2pt,
  )
  show table.cell: it => {
    set text(size: 9.35pt)
    set par(justify: false, leading: 0.62em)
    it
  }
  show table.cell.where(y: 0): it => {
    set text(size: 9.35pt, weight: 650, fill: proposal-blue)
    set par(justify: false)
    it
  }
  set table(
    inset: (x: 5.5pt, y: 4.5pt),
    align: (x, y) => if y == 0 { center + horizon } else { left + horizon },
    stroke: (x, y) => if y == 0 {
      (
        top: 0.75pt + proposal-blue,
        bottom: 0.75pt + proposal-blue,
        left: none,
        right: none,
      )
    } else {
      (
        top: none,
        bottom: 0.25pt + proposal-rule,
        left: none,
        right: none,
      )
    },
    fill: (x, y) => if y == 0 {
      proposal-blue.lighten(92%)
    } else if calc.odd(y) {
      proposal-paper
    },
  )
  body
}

#let thesis-box(title, body) = block(above: 0.9em, below: 1em, breakable: true)[
  #rect(
    width: 100%,
    radius: 4pt,
    inset: (x: 10pt, y: 8pt),
    fill: proposal-blue.lighten(94%),
    stroke: 0.55pt + proposal-blue.lighten(55%),
  )[
    #text(size: 8.7pt, weight: 700, fill: proposal-red)[#smallcaps(title)]
    #v(3pt)
    #set text(fill: proposal-ink)
    #body
  ]
]

#let ladder-step(kicker, label, body) = rect(
  width: 100%,
  radius: 4pt,
  inset: 7pt,
  fill: white,
  stroke: 0.45pt + proposal-rule,
)[
  #text(size: 7.6pt, weight: 700, fill: proposal-red)[#smallcaps(kicker)]
  #v(2pt)
  #text(size: 10.2pt, weight: 700, fill: proposal-blue)[#label]
  #v(3pt)
  #text(size: 8.4pt, fill: proposal-muted)[#body]
]

#let rollout-ladder() = block(above: 0.8em, below: 1em)[
  #grid(
    columns: (1fr, auto, 1fr, auto, 1fr),
    column-gutter: 5pt,
    align: horizon,
    ladder-step([Branch set], [#raw("ArgTopK")], [select the inspected candidate budget]),
    text(size: 11pt, fill: proposal-muted)[#sym.arrow.r],
    ladder-step([Greedy], [#raw("ArgTop1_1")], [choose the best immediate RRI view]),
    text(size: 11pt, fill: proposal-muted)[#sym.arrow.r],
    ladder-step([Lookahead], [#raw("ArgTop1_h")], [choose the first action of an h-step rollout]),
  )
]
