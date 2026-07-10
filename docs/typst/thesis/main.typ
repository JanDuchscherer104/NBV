#import "template/layout/thesis_template.typ": *
#import "metadata.typ": *
#import "../shared/macros.typ": *
#import "../shared/glossary.typ": *
#import "../shared/notation.typ": print-thesis-symbols
#import "draft_markers.typ": *
#import "@preview/booktabs:0.0.4": *

#set document(title: titleEnglish, author: author)
#set text(font: "New Computer Modern")

#show: booktabs-default-table-style
#show: make-glossary
#register-aria-glossary()

#show: thesis.with(
  title: titleEnglish,
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
  abstract_en: [
    This thesis investigates target-conditioned, quality-driven @next-best-view planning for egocentric 3D reconstruction in @aria-synthetic-environments. It uses target-specific @relative-reconstruction-improvement as the supervision and evaluation signal for finite candidate view selection, measures bounded oracle-lookahead headroom, and tests whether an actor-visible finite-horizon value model can recover part of that headroom under matched oracle re-evaluation.

    #validation_todo(
      [Rewrite this proposal-style abstract from the frozen evidence. The final abstract must distinguish training reward from endpoint evaluation, report the principal quantitative result and uncertainty, state the supported conclusion, and name the main limitation.],
      source: [thesis peer review; current results scaffold; thesis questions and roadmap],
      gate: [final results and claim freeze],
    )
  ],
  abstract_de: [
    #question_todo(
      [Write the German abstract after the English thesis claim and final evidence scale are stable.],
      source: [main thesis seed],
    )
  ],
  acknowledgement: [
    #question_todo([Fill acknowledgements close to submission.], source: [main thesis seed])
  ],
  transparency_ai_tools: [
    AI-assisted tools were used to organize literature notes, check consistency across repository documentation, and draft parts of the thesis seed. The author remains responsible for the final research scope, technical claims, citations, implementation, experiments, and submitted document. #validation_todo([Update this statement against final institutional requirements before submission.], source: [proposal transparency text])
  ],
  front_matter_after_contents: [
    #heading(numbering: none, outlined: false)[Glossary and Abbreviations]
    #print-aria-glossary(
      show-all: true,
      disable-back-references: true,
      user-print-group-heading: (group, level: none) => heading(
        level: 2,
        numbering: none,
        outlined: false,
      )[#group],
    )

    #pagebreak()
    #heading(numbering: none, outlined: false)[List of Symbols]
    #print-thesis-symbols()
  ],
  appendix_content: [
    #include "appendix/index.typ"
  ],
)

#include "sections/01-introduction.typ"
#include "sections/02-foundations/index.typ"
#include "sections/03-oracle-and-data-generation/index.typ"
#include "sections/04-method/index.typ"
#include "sections/05-experimental-design/index.typ"
#include "sections/06-results.typ"
#include "sections/07-discussion.typ"
#include "sections/08-conclusion.typ"
