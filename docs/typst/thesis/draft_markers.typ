#import "@preview/dashy-todo:0.1.3": todo as dashy_todo

#let thesis_mode = sys.inputs.at("aria-thesis-mode", default: "development")

#let implementation_states = ("implemented", "partial", "planned", "exploratory")
#let evidence_states = ("validated", "pending", "conflicted", "not-applicable")

#if thesis_mode not in ("development", "submission") {
  panic("aria-thesis-mode must be either development or submission")
}

// Development-only material is omitted from submission output while retaining
// a single, explicit guard at every draft-content boundary.
#let development_only(body) = if thesis_mode == "development" { body() }
#let submission_only(body) = if thesis_mode == "submission" { body() }

#let promotion_dispositions = ("candidate", "blocked", "deferred", "rejected")

#let _required_promotion_field(name, value) = {
  if value == none { panic("promotion_entry requires a non-empty " + name) }
  if type(value) == str and value.trim().len() == 0 or repr(value) == "[]" { panic("promotion_entry requires a non-empty " + name) }
  value
}

#let promotion_entry(summary, source: none, target-section: none, gate: none, disposition: none) = development_only(() => {
  let summary = _required_promotion_field("summary", summary)
  let source = _required_promotion_field("source", source)
  let target = _required_promotion_field("target-section", target-section)
  let gate = _required_promotion_field("gate", gate)
  let disposition = _required_promotion_field("disposition", disposition)
  if type(disposition) != str or disposition not in promotion_dispositions { panic("Unknown promotion disposition: " + repr(disposition)) }
  block(breakable: false)[
    #text(size: 8.4pt)[*Promotion queue — #disposition:* #summary \
      #text(size: 7.6pt)[Source: #source; target: #target; gate: #gate]]
  ]
})

#let todo_marker(kind, body, stroke: orange, source: none, gate: none) = if thesis_mode == "submission" {
  panic("Unresolved thesis marker in submission mode: " + repr(kind))
} else { block(breakable: false)[
  #text(size: 9pt)[
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
] }

#let impl_todo(body, source: none, gate: none) = todo_marker([Implementation TODO], body, stroke: blue, source: source, gate: gate)
#let research_todo(body, source: none, gate: none) = todo_marker([Research TODO], body, stroke: purple, source: source, gate: gate)
#let decision_todo(body, source: none, gate: none) = todo_marker([Open decision], body, stroke: orange, source: source, gate: gate)
#let question_todo(body, source: none, gate: none) = todo_marker([Open question], body, stroke: teal, source: source, gate: gate)
#let conflict_todo(body, source: none, gate: none) = todo_marker([Conflict], body, stroke: red, source: source, gate: gate)
#let validation_todo(body, source: none, gate: none) = todo_marker([Validation TODO], body, stroke: olive, source: source, gate: gate)
#let prune_todo(body, source: none, gate: none) = todo_marker([Remove or rewrite before submission], body, stroke: gray, source: source, gate: gate)
#let archive_note(body, source: none) = todo_marker([Archived source note], body, stroke: gray, source: source)

#let implementation_colour(state) = if state == "implemented" {
  rgb("#217A3C")
} else if state == "partial" {
  rgb("#2166A5")
} else if state == "planned" {
  rgb("#6B46A5")
} else {
  rgb("#5F6368")
}

#let evidence_colour(state) = if state == "validated" {
  rgb("#217A3C")
} else if state == "pending" {
  rgb("#A15C00")
} else if state == "conflicted" {
  rgb("#B3261E")
} else {
  rgb("#5F6368")
}

// Editorial status belongs only in the development render. Its scientific
// substance must become ordinary limitation, method, or result prose before
// submission rather than leaking a project-management box into the thesis.
#let thesis_status(
  body,
  implementation: none,
  evidence: none,
  citation: none,
  source: none,
  gate: none,
) = {
  if thesis_mode == "submission" {
    panic("Development-only thesis status block in submission mode")
  }
  if implementation not in implementation_states {
    panic("Unknown thesis implementation state: " + repr(implementation))
  }
  if evidence not in evidence_states {
    panic("Unknown thesis evidence state: " + repr(evidence))
  }

  let impl_colour = implementation_colour(implementation)
  let ev_colour = evidence_colour(evidence)

  block(above: 0.7em, below: 0.8em, breakable: false)[
    #rect(
      width: 100%,
      radius: 3pt,
      inset: (x: 9pt, y: 7pt),
      fill: impl_colour.lighten(95%),
      stroke: 0.55pt + ev_colour.lighten(42%),
    )[
      #text(size: 8.2pt, weight: 700, fill: impl_colour)[Implementation: #implementation]
      #h(0.8em)
      #text(size: 8.2pt, weight: 700, fill: ev_colour)[Evidence: #evidence]
      #v(3pt)
      #text(size: 8.5pt)[#body]
      #if citation != none [
        \
        #text(size: 7.6pt)[Literature: #citation]
      ]
      #if gate != none [
        \
        #text(size: 7.6pt)[Promotion gate: #gate]
      ]
      #if source != none [
        \
        #text(size: 7.6pt, fill: gray)[Development source: #source]
      ]
    ]
  ]
}

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
