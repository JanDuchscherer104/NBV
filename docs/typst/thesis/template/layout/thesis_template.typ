#import "titlepage.typ": *
#import "disclaimer.typ": *
#import "acknowledgement.typ": acknowledgement as acknowledgement_layout
#import "transparency_ai_tools.typ": transparency_ai_tools as transparency_ai_tools_layout
#import "abstract.typ": *
#import "fonts.typ": *
#import "branding.typ": hm-colors
#import "../utils/print_page_break.typ": *
#import "../utils/diagram.typ": in-outline
#import "../utils/fr_qa_c.typ": fr_counter, qa_counter, const_counter

#let thesis(
  title: "",
  titleGerman: "",
  thesisKindEnglish: "Master's Thesis",
  thesisKindGerman: "Masterarbeit",
  academicDegree: "Master of Science (M.Sc.)",
  program: "",
  specialization: "",
  universityEnglish: "",
  universityGerman: "",
  facultyEnglish: "",
  facultyGerman: "",
  firstExaminer: "",
  secondExaminer: "",
  supervisors: (),
  author: "",
  email: "",
  matriculationNumber: "",
  startDate: none,
  submissionDate: none,
  submissionDateText: "",
  abstract_en: "",
  abstract_de: "",
  acknowledgement: "",
  transparency_ai_tools: "",
  front_matter_after_contents: none,
  appendix_content: none,
  is_print: false,
  body,
) = {
  titlepage(
    title: title,
    titleGerman: titleGerman,
    thesisKindEnglish: thesisKindEnglish,
    thesisKindGerman: thesisKindGerman,
    academicDegree: academicDegree,
    program: program,
    specialization: specialization,
    universityEnglish: universityEnglish,
    universityGerman: universityGerman,
    facultyEnglish: facultyEnglish,
    facultyGerman: facultyGerman,
    firstExaminer: firstExaminer,
    secondExaminer: secondExaminer,
    supervisors: supervisors,
    author: author,
    email: email,
    matriculationNumber: matriculationNumber,
    startDate: startDate,
    submissionDate: submissionDate,
    submissionDateText: submissionDateText,
  )

  print_page_break(print: is_print, to: "even")
  transparency_ai_tools_layout(transparency_ai_tools)

  print_page_break(print: is_print)
  acknowledgement_layout(acknowledgement)

  print_page_break(print: is_print)
  abstract(lang: "en")[#abstract_en]
  abstract(lang: "de")[#abstract_de]

  set page(
    margin: (left: 30mm, right: 30mm, top: 40mm, bottom: 40mm),
    numbering: none,
    number-align: center,
  )

  set text(font: fonts.body, size: 12pt, lang: "en")
  show math.equation: set text(weight: 400)

  show heading: set block(below: 0.85em, above: 1.75em)
  show heading: set text(font: fonts.body)
  set heading(numbering: "1.1")
  show ref: it => {
    let el = it.element
    if el != none and el.func() == heading and el.level == 1 {
      link(el.location(), [Chapter #numbering(el.numbering, ..counter(heading).at(el.location()))])
    } else if el != none and el.func() == figure and el.kind == "FR" {
      link(el.location(), [#el.supplement#numbering(el.numbering, ..fr_counter.at(el.location()))])
    } else if el != none and el.func() == figure and el.kind == "QA" {
      link(el.location(), [#el.supplement#numbering(el.numbering, ..qa_counter.at(el.location()))])
    } else if el != none and el.func() == figure and el.kind == "C" {
      link(el.location(), [#el.supplement#numbering(el.numbering, ..const_counter.at(el.location()))])
    } else {
      it
    }
  }

  set par(leading: 1em)
  set cite(style: "alphanumeric")
  show figure.where(kind: image): set text(size: 0.85em)
  show figure.where(kind: table): set text(size: 0.85em)
  show figure.where(kind: "FR"): set text(size: 0.85em)
  show figure.where(kind: "QA"): set text(size: 0.85em)
  show figure.where(kind: "C"): set text(size: 0.85em)

  show outline.entry.where(level: 1): it => {
    v(15pt, weak: true)
    strong(it)
  }
  outline(
    title: {
      text(font: fonts.body, 1.5em, weight: 700, fill: hm-colors.blue, "Contents")
      v(15mm)
    },
    indent: 2em,
  )

  if front_matter_after_contents != none {
    pagebreak()
    front_matter_after_contents
  } else {
    v(2.4fr)
  }

  pagebreak()
  heading(numbering: none)[List of Figures]
  show outline: it => {
    in-outline.update(true)
    it
    in-outline.update(false)
  }
  outline(title: "", target: figure.where(kind: image))

  context[
    #if query(figure.where(kind: table)).len() > 0 {
      pagebreak()
      heading(numbering: none)[List of Tables]
      outline(title: "", target: figure.where(kind: table))
    }
  ]
  pagebreak()

  set page(numbering: "1")
  counter(page).update(1)
  set par(justify: true, first-line-indent: 2em)

  show heading.where(level: 1): it => {
    pagebreak(weak: true)
    it
  }
  body

  pagebreak()
  bibliography("/references.bib", style: "ieee")

  if appendix_content != none {
    pagebreak()
    counter(heading).update(0)
    set heading(numbering: "A.1")
    appendix_content
  }

  pagebreak()
  disclaimer(
    title: title,
    thesisKindGerman: thesisKindGerman,
    author: author,
    submissionDate: submissionDate,
    submissionDateText: submissionDateText,
  )
}
