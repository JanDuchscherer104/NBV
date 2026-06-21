#import "template/layout/proposal_template.typ": *
#import "metadata.typ": *
#import "../shared/macros.typ": *
#import "../shared/glossary.typ": *
#import "sections/proposal/_style.typ": *

#let proposalTitleEnglish = "ARIA-NBV: Target-Conditioned, Quality-Driven Next-Best-View Planning"
#let proposalTitleGerman = "ARIA-NBV: Zielkonditionierte, qualitaetsgetriebene Next-Best-View-Planung"

#set document(title: proposalTitleEnglish + " Proposal", author: author)
#set text(font: "New Computer Modern")

#show: make-glossary.with(link: false)
#register-aria-glossary()

#show: proposal.with(
  title: proposalTitleEnglish,
  titleGerman: proposalTitleGerman,
  thesisKindEnglish: thesisKindEnglish + " Proposal",
  thesisKindGerman: "Proposal zur " + thesisKindGerman,
  academicDegree: academicDegree,
  program: program,
  specialization: specialization,
  universityEnglish: universityEnglish,
  universityGerman: universityGerman,
  facultyEnglish: facultyEnglish,
  facultyGerman: facultyGerman,
  firstExaminer: firstExaminer,
  secondExaminer: "",
  supervisors: supervisors,
  author: author,
  email: email,
  matriculationNumber: matriculationNumber,
  startDate: startDate,
  submissionDate: datetime(day: 30, month: 4, year: 2026),
  submissionDateText: "30 April 2026",
  transparency_ai_tools: [
    AI-assisted tools were used to organize literature notes, check consistency across repository documentation, and draft parts of the proposal text. The author remains responsible for the final research scope, technical claims, citations, and submitted document.
  ],
)

#show: proposal-style

#include "sections/proposal/01-motivation.typ"
#include "sections/proposal/02-problem.typ"
#include "sections/proposal/02-related-work.typ"
#include "sections/proposal/03-objectives.typ"
#include "sections/proposal/04-method.typ"
#include "sections/proposal/05-schedule.typ"
#include "sections/proposal/06-outline.typ"
