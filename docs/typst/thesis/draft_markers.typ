#import "@preview/dashy-todo:0.1.3": todo as dashy_todo

#let todo_marker(kind, body, stroke: orange, source: none, gate: none) = text(size: 9pt)[
  #dashy_todo(position: "inline", stroke: stroke)[
    *#kind:* #body
    #if source != none [
      \
      #text(size: 7.6pt)[Source: #source]
    ]
    #if gate != none [
      \
      #text(size: 7.6pt)[Gate: #gate]
    ]
  ]
]

#let impl_todo(body, source: none, gate: none) = todo_marker([Implementation TODO], body, stroke: blue, source: source, gate: gate)
#let research_todo(body, source: none, gate: none) = todo_marker([Research TODO], body, stroke: purple, source: source, gate: gate)
#let decision_todo(body, source: none, gate: none) = todo_marker([Open decision], body, stroke: orange, source: source, gate: gate)
#let question_todo(body, source: none, gate: none) = todo_marker([Open question], body, stroke: teal, source: source, gate: gate)
#let conflict_todo(body, source: none, gate: none) = todo_marker([Conflict], body, stroke: red, source: source, gate: gate)
#let validation_todo(body, source: none, gate: none) = todo_marker([Validation TODO], body, stroke: olive, source: source, gate: gate)
#let archive_note(body, source: none) = todo_marker([Archived source note], body, stroke: gray, source: source)

#let thesis_box(title, body) = block(above: 0.9em, below: 1em, breakable: true)[
  #rect(
    width: 100%,
    radius: 4pt,
    inset: (x: 10pt, y: 8pt),
    fill: rgb("#003B70").lighten(94%),
    stroke: 0.55pt + rgb("#003B70").lighten(55%),
  )[
    #text(size: 8.7pt, weight: 700, fill: rgb("#fc5555"))[#smallcaps(title)]
    #v(3pt)
    #body
  ]
]
