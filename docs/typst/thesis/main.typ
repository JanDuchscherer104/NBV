#import "template/layout/thesis_template.typ": *
#import "metadata.typ": *
#import "../shared/macros.typ": *
#import "../shared/glossary.typ": make-glossary as make-aria-glossary, register-aria-glossary, print-aria-glossary
#import "../shared/notation.typ": print-thesis-symbols
#import "experiment_data.typ": thesis-report-settings, load-thesis-report
#import "draft_markers.typ": development_only

#let report-settings = thesis-report-settings()
#let _publication-gate = load-thesis-report(
  report-settings.path,
  evidence-status: report-settings.evidence-status,
  required-role: report-settings.required-role,
)

#set document(title: titleEnglish, author: author)
#set text(font: "New Computer Modern")

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
    Active perception couples sensing and reconstruction: what can be reconstructed depends on what a sensing action makes visible. Under a limited acquisition budget, next-best-view planning must therefore choose which feasible observation should come next. The literature reviewed in Chapter 2 treats scene coverage, one-step reconstruction-quality ranking, target-aware information criteria, and sequential coverage separately, but leaves their conjunction for target-specific egocentric reconstruction unresolved. This thesis studies that conjunction as finite candidate selection under hard validity constraints in @aria-synthetic-environments. It adapts @relative-reconstruction-improvement to a target-cropped point--mesh objective, separates privileged task construction and oracle evaluation from the deployable actor path, and marks GT-derived target or selected-depth inputs as non-deployable controls. The primary experiment first tests whether bounded oracle lookahead provides endpoint-quality headroom over one-step oracle greedy; a learned policy is evaluated only if that headroom passes a prespecified meaningful-effect and uncertainty rule. The current implementation supports target-specific oracle scoring and selected-action replay, with rendering memory limiting scale. Actor-visible target matching, metric repeatability, a validated held-out population, headroom, and paired policy outcomes remain unestablished. The present contribution is therefore an auditable method and experimental design, not evidence of policy superiority or deployment readiness.
  ],
  abstract_de: [
    Aktive Wahrnehmung beruht auf einer geometrischen Prämisse: Was rekonstruiert werden kann, hängt davon ab, was eine Sensorhandlung sichtbar macht. Bei begrenztem Aufnahmebudget muss die Next-Best-View-Planung daher entscheiden, welche zulässige Beobachtung als Nächstes erfolgen soll. Die in Kapitel 2 ausgewertete Literatur behandelt Szenenabdeckung, einstufige Rekonstruktionsqualität, zielbezogene Informationsmaße und sequenzielle Abdeckung getrennt, lässt deren Verbindung für die zielspezifische egozentrische Rekonstruktion jedoch offen. Diese Arbeit untersucht diese Verbindung als Auswahl aus einer endlichen Kandidatenmenge unter harten Zulässigkeitsbedingungen in @aria-synthetic-environments. Sie überträgt die @relative-reconstruction-improvement auf ein zielbeschnittenes Punkt--Mesh-Maß, trennt privilegierte Aufgabenerzeugung und Orakelevaluation vom einsatzfähigen Akteurpfad und kennzeichnet GT-basierte Ziel- oder Tiefeneingaben als nicht einsetzbare Kontrollen. Das primäre Experiment prüft zunächst, ob eine beschränkte Orakelvorausschau gegenüber einer einstufigen gierigen Orakelstrategie einen Vorteil bei der Endpunktqualität bietet; eine gelernte Strategie wird nur bewertet, wenn dieser Vorteil ein vorab festgelegtes Relevanz- und Unsicherheitskriterium erfüllt. Die aktuelle Implementierung unterstützt zielspezifische Orakelbewertung und Replay ausgewählter Aktionen, wobei der Speicherbedarf des Renderers die Skalierung begrenzt. Nicht belegt sind bislang eine beobachtungsbasierte Zielzuordnung, die Wiederholbarkeit des Qualitätsmaßes, eine validierte zurückgehaltene Studienpopulation, ein Vorteil der Orakelvorausschau und gepaarte Strategieergebnisse. Der gegenwärtige Beitrag ist daher ein prüfbarer Methoden- und Versuchsaufbau, kein Nachweis für Strategieüberlegenheit oder Einsatzreife.
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

// Development planning and gate reports own their own lazy development-only
// boundaries, so they can also be compiled as standalone development sources.
#include "development/roadmap.typ"
#include "development/s2-rollout-pilot.typ"
#include "development/method-alternatives.typ"
