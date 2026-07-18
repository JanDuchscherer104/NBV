#import "fonts.typ": *
#import "branding.typ": hm-brand, hm-colors

#let titlepage(
  title: "",
  titleGerman: "",
  thesisKindEnglish: "Master's Thesis",
  thesisKindGerman: "Masterarbeit",
  academicDegree: "Master of Science (M.Sc.)",
  program: "",
  specialization: "",
  universityEnglish: hm-brand.organization,
  universityGerman: "Hochschule Muenchen",
  facultyEnglish: hm-brand.department,
  facultyGerman: "Fakultaet fuer Informatik und Mathematik",
  firstExaminer: "",
  secondExaminer: "",
  supervisors: (),
  author: "",
  email: "",
  matriculationNumber: "",
  startDate: none,
  submissionDate: none,
  submissionDateText: "",
) = {
  let compact-table(entries) = {
    align(
      center,
      grid(
        columns: (auto, 1fr),
        gutter: 0.75em,
        align: left,
        ..for (term, desc) in entries {
          ([*#term:*], desc)
        },
      )
    )
  }

  set page(
    margin: (left: 24mm, right: 24mm, top: 20mm, bottom: 18mm),
    numbering: none,
    number-align: center,
  )

  set text(font: fonts.body, size: 10.5pt, lang: "en")
  set par(leading: 0.5em)

  place(top + right, rect(width: 100%, height: 4mm, fill: hm-colors.blue))

  v(4mm)
  align(center, image(hm-brand.logo, width: 23%))

  v(6mm)
  align(center, text(font: fonts.sans, 1.55em, weight: 700, fill: hm-colors.blue, universityEnglish))

  v(1.5mm)
  align(center, text(font: fonts.sans, 0.9em, weight: 500, universityGerman))

  v(3mm)
  align(center, text(font: fonts.sans, 0.98em, weight: 500, facultyEnglish))

  v(1mm)
  align(center, text(font: fonts.sans, 0.9em, weight: 500, facultyGerman))

  v(10mm)
  align(center, text(font: fonts.sans, 1.45em, weight: 700, fill: hm-colors.dark-blue, title))

  if titleGerman != "" {
    v(2.5mm)
    align(center, emph(text(font: fonts.sans, 1.05em, titleGerman)))
  }

  v(10mm)
  align(center, text(font: fonts.sans, 1.18em, weight: 700, thesisKindEnglish + " / " + thesisKindGerman))
  v(1.5mm)
  align(center, text(0.9em)[for obtaining the academic degree #academicDegree])

  v(9mm)
  align(center, text(0.9em)[
    submitted to\
    #universityEnglish\
    #facultyEnglish
  ])

  v(8mm)
  let authorEntries = ()
  authorEntries.push(("Submitted by", author))
  if email != "" {
    authorEntries.push(("Email", email))
  }
  authorEntries.push(("Program", program))
  if specialization != "" {
    authorEntries.push(("Specialization", specialization))
  }
  authorEntries.push(("Matriculation Number", matriculationNumber))
  compact-table(authorEntries)

  v(10mm)
  let examEntries = ()
  if firstExaminer != none and firstExaminer != "" {
    examEntries.push(("First Examiner", firstExaminer))
  }
  if secondExaminer != none and secondExaminer != "" {
    examEntries.push(("Second Examiner", secondExaminer))
  }
  if supervisors.len() > 0 {
    let supervisorField = "Supervisor" + if supervisors.len() > 1 { "s" } else { "" }
    examEntries.push((supervisorField, supervisors.join(", ")))
  }
  if submissionDateText != "" {
    examEntries.push(("Submission Date", submissionDateText))
  } else if submissionDate != none {
    examEntries.push(("Submission Date", submissionDate.display("[day].[month].[year]")))
  }
  compact-table(examEntries)
}
