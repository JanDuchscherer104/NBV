#import "fonts.typ": *
#import "branding.typ": hm-colors

#let disclaimer(
  title: "",
  thesisKindGerman: "Abschlussarbeit",
  author: "",
  submissionDate: none,
  submissionDateText: "",
) = {
  set page(
    margin: (left: 30mm, right: 30mm, top: 40mm, bottom: 40mm),
    numbering: none,
    number-align: center,
  )

  set text(font: fonts.body, size: 12pt, lang: "de")
  set par(leading: 1em, justify: true)

  align(left, text(font: fonts.sans, 20pt, weight: 700, fill: hm-colors.blue, "Ehrenwoertliche Erklaerung"))
  v(14mm)

  [Ich versichere, dass ich diese #thesisKindGerman selbststaendig verfasst und keine anderen als die angegebenen Quellen und Hilfsmittel benutzt habe.]

  v(18mm)
  if submissionDateText != "" or submissionDate != none {
    grid(
      columns: 2,
      gutter: 1fr,
      "Muenchen, " + if submissionDateText != "" { submissionDateText } else { submissionDate.display("[day].[month].[year]") },
      author,
    )
  } else {
    align(right, author)
  }
}
