#import "../draft_markers.typ": development_only

#let reader-state = toml("reader-state.toml")
#let expected-order = (
  "introduction",
  "foundations",
  "oracle-data",
  "method",
  "experimental-design",
  "results",
  "discussion",
  "conclusion",
)

#let required-text(record, field, owner) = {
  let value = record.at(field, default: none)
  if type(value) != str or value.trim().len() == 0 {
    panic(owner + " requires non-empty " + field)
  }
  value
}

#let required-list(record, field, owner, min: 1, max: 4) = {
  let value = record.at(field, default: none)
  if type(value) != array {
    panic(owner + " requires array field " + field)
  }
  if value.len() < min or value.len() > max {
    panic(
      owner + "." + field + " requires " + repr(min) + "--" + repr(max)
      + " entries",
    )
  }
  if not value.all(item => type(item) == str and item.trim().len() > 0) {
    panic(owner + "." + field + " requires non-empty string entries")
  }
  value
}

#let chapters = {
  let meta = reader-state.at("meta", default: none)
  if type(meta) != dictionary {
    panic("reader-state.toml requires [meta]")
  }
  let _schema = required-text(meta, "schema", "reader-state.meta")
  let _owner = required-text(meta, "owner", "reader-state.meta")
  let _purpose = required-text(meta, "purpose", "reader-state.meta")
  let _maintenance = required-text(meta, "maintenance", "reader-state.meta")
  let chapter-order = meta.at("chapter_order", default: none)
  if chapter-order != expected-order {
    panic(
      "reader-state.meta.chapter_order must equal " + repr(expected-order),
    )
  }

  let values = reader-state.at("chapters", default: none)
  if type(values) != array {
    panic("reader-state.toml requires [[chapters]] records")
  }
  let ids = values.map(chapter => chapter.at("id", default: none))
  if ids != expected-order {
    panic("reader-state chapter order must equal " + repr(expected-order))
  }

  for (index, chapter) in values.enumerate() {
    let owner = "reader-state.chapters[" + repr(index) + "]"
    let _id = required-text(chapter, "id", owner)
    let _title = required-text(chapter, "title", owner)
    let _source = required-text(chapter, "source", owner)
    let _question = required-text(chapter, "reader_question", owner)
    let _enters = required-list(chapter, "enters_knowing", owner, max: 3)
    let _assumptions = required-list(chapter, "must_not_assume", owner, max: 3)
    let _resolves = required-text(chapter, "resolves", owner)
    let _leaves = required-list(chapter, "leaves_knowing", owner, max: 3)
    let _enables = required-text(chapter, "enables", owner)
    let _teaching = required-text(chapter, "teaching_device", owner)
    let _threads = required-list(chapter, "theory_threads", owner, max: 4)

    let expected-next = if index + 1 < expected-order.len() {
      expected-order.at(index + 1)
    } else {
      none
    }
    let actual-next = chapter.at("next_chapter", default: none)
    if actual-next != expected-next {
      panic(
        owner + ".next_chapter must equal " + repr(expected-next),
      )
    }
  }
  values
}

#let compact-list(items) = {
  set text(size: 7.5pt)
  set par(leading: 0.48em)
  for item in items [
    - #item
  ]
}

#let field(title, body) = [
  #text(size: 7.2pt, weight: 700, fill: rgb("#003B70"))[#title]
  #v(1.5pt)
  #text(size: 7.7pt)[#body]
]

#let chapter-card(chapter, index) = block(
  above: 0.65em,
  below: 0.75em,
  breakable: false,
)[
  #rect(
    width: 100%,
    radius: 3pt,
    inset: (x: 8pt, y: 7pt),
    fill: rgb("#003B70").lighten(96%),
    stroke: 0.55pt + rgb("#003B70").lighten(55%),
  )[
    #text(size: 9pt, weight: 700)[
      Chapter #(index + 1): #chapter.title
    ]
    #h(0.6em)
    #text(size: 6.8pt, fill: gray)[#chapter.source]
    #v(5pt)

    #field([Reader question], chapter.reader_question)
    #v(5pt)

    #grid(
      columns: (1fr, 1fr),
      gutter: 10pt,
      [
        #field([Enters knowing], compact-list(chapter.enters_knowing))
        #v(4pt)
        #field([Must not assume], compact-list(chapter.must_not_assume))
        #v(4pt)
        #field([Teaching device], chapter.teaching_device)
      ],
      [
        #field([Resolves], chapter.resolves)
        #v(4pt)
        #field([Leaves knowing], compact-list(chapter.leaves_knowing))
        #v(4pt)
        #field([Enables], chapter.enables)
      ],
    )
    #v(4pt)
    #text(size: 7pt, weight: 700, fill: rgb("#6B46A5"))[Theory threads:]
    #h(0.45em)
    #text(size: 7.2pt)[#chapter.theory_threads.join(" · ")]
  ]
]

#development_only(() => [
  #pagebreak()
  #heading(level: 1, numbering: none)[Reader-state ledger] <ch:reader-state-ledger>
  #metadata(reader-state.meta.schema) <reader-state-schema>
  #metadata(chapters.map(chapter => chapter.id)) <reader-state-chapter-order>

  This development-only ledger records the intended learning journey of the
  thesis. It is an editorial contract, not a generated summary and not an owner
  of scientific claims. Chapter prose, equations, figures, and evidence remain
  with their active sources. The ledger makes their pedagogical dependency
  explicit so that an authoring agent can preserve what the reader knows,
  what the chapter must teach, and what the next chapter may safely assume.

  #for (index, chapter) in chapters.enumerate() {
    chapter-card(chapter, index)
  }

  #heading(level: 2, numbering: none)[Maintenance contract] <ssec:reader-state-maintenance>

  `reader-state.toml` is authored rather than inferred. Update the affected
  chapter record in the same change whenever its central reader question,
  prerequisites, durable takeaways, teaching device, or outgoing dependency
  changes. Copy editing, citation repair, and layout-only changes do not require
  a ledger update unless they alter that learning journey. Development
  compilation validates the schema and renders these cards; submission mode
  omits them completely.
])
