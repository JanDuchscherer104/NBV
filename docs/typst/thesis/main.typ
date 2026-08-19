#import "template/layout/thesis_template.typ": *
#import "metadata.typ": *
#import "../shared/macros.typ": *
#import "glossary-overrides.typ": make-aria-glossary, register-aria-glossary, print-aria-glossary
#import "../shared/notation.typ": print-thesis-symbols
#import "experiment_data.typ": thesis-report-settings, load-thesis-report
#import "draft_markers.typ": development_only
#import "@preview/booktabs:0.0.4": *

#let report-settings = thesis-report-settings()
#let _publication-gate = load-thesis-report(
  report-settings.path,
  evidence-status: report-settings.evidence-status,
  required-role: report-settings.required-role,
)

#set document(title: titleEnglish, author: author)
#set text(font: "New Computer Modern")

#show: booktabs-default-table-style
#show: make-aria-glossary
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
    This thesis studies target-conditioned, quality-driven @next-best-view planning for egocentric 3D reconstruction in @aria-synthetic-environments. It defines target-specific @relative-reconstruction-improvement as an oracle signal, constructs finite candidate and replay contracts, and separates privileged label generation from the actor-visible inputs available to a learned finite-horizon value model. The evaluation is designed to measure oracle-lookahead headroom and the fraction recovered by a learned policy under matched oracle re-evaluation. The evidence available for this version establishes the evaluation contract and implementation readiness, but does not contain confirmatory held-out policy outcomes; it therefore supports no claim that a learned policy improves over the specified baselines. The main remaining limitation is the absence of a validated, population-level rollout bundle with paired endpoint estimates and uncertainty.
  ],
  abstract_de: [
    Diese Arbeit untersucht zielkonditionierte, qualitätsgetriebene Planung der nächsten besten Ansicht für die egozentrische 3D-Rekonstruktion in @aria-synthetic-environments. Sie definiert die zielspezifische @relative-reconstruction-improvement als Orakelsignal, legt Verträge für endliche Kandidatenmengen und Replay-Daten fest und trennt die privilegierte Erzeugung von Trainingssignalen von den für ein gelerntes Modell mit endlichem Horizont sichtbaren Eingaben. Die Evaluation soll den Spielraum einer vorausschauenden Orakelstrategie und den durch eine gelernte Strategie erreichten Anteil unter identischer Orakel-Neubewertung messen. Die für diese Fassung verfügbare Evidenz belegt den Evaluationsvertrag und die Implementierungsbereitschaft, enthält jedoch keine bestätigenden Ergebnisse auf zurückgehaltenen Daten. Daher wird keine Überlegenheit einer gelernten Strategie gegenüber den festgelegten Baselines behauptet. Die wesentliche verbleibende Einschränkung ist das Fehlen eines validierten Rollout-Datensatzes auf Populationsebene mit gepaarten Endpunktschätzungen und Unsicherheitsangaben.
  ],
  acknowledgement: [
    Acknowledgements are omitted from this version.
  ],
  transparency_ai_tools: [
    Generative-AI tools supported literature-note organization, consistency checks, and language revision. The author selected the research questions, verified sources and technical claims, implemented and evaluated the system, and remains responsible for the submitted work.
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
  appendix_content: [#include "appendix/index.typ"],
)

#include "sections/01-introduction.typ"
#include "sections/02-foundations/index.typ"
#include "sections/03-oracle-and-data-generation/index.typ"
#include "sections/04-method/index.typ"
#include "sections/05-experimental-design/index.typ"
#include "sections/06-results.typ"
#include "sections/07-discussion.typ"
#include "sections/08-conclusion.typ"

// Development planning and gate reports are omitted from submission output.
#development_only(() => [
  #include "development/roadmap.typ"
  #include "development/m1-contract-report.typ"
])
