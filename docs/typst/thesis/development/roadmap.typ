#import "../draft_markers.typ": development_only, promotion_entry, thesis_status
#import "../../shared/tables.typ": development-table

#let roadmap = toml("roadmap.toml")
#let snapshot-colours = (
  done: rgb("#217A3C"),
  now: rgb("#2166A5"),
  blocked: rgb("#B3261E"),
  next: rgb("#6B46A5"),
)
#let milestone-colours = (
  done: rgb("#217A3C"),
  "in-progress": rgb("#2166A5"),
  planned: rgb("#6B46A5"),
  buffer: rgb("#5F6368"),
)
#let snapshot-labels = (done: [Done], now: [Now], blocked: [Blocked], next: [Next])
#let milestone-labels = (
  done: [done],
  "in-progress": [in progress],
  planned: [planned],
  buffer: [safety buffer],
)

#let snapshot-card(entry) = {
  let colour = snapshot-colours.at(entry.kind)
  rect(
    width: 100%,
    radius: 3pt,
    inset: (x: 7pt, y: 6pt),
    fill: colour.lighten(95%),
    stroke: .55pt + colour.lighten(45%),
  )[
    #text(size: 7.2pt, weight: 700, fill: colour)[#snapshot-labels.at(entry.kind)]
    #h(.5em)
    #text(size: 8pt, weight: 700)[#entry.title]
    #v(2.5pt)
    #text(size: 7.3pt)[#entry.body]
  ]
}

#let gate-card(milestone) = {
  let colour = milestone-colours.at(milestone.status)
  rect(
    width: 100%,
    radius: 2.5pt,
    inset: (x: 4pt, y: 4pt),
    fill: colour.lighten(95%),
    stroke: .5pt + colour.lighten(45%),
  )[
    #align(center)[
      #text(size: 6.5pt, weight: 700, fill: colour)[#milestone.id]
      #linebreak()
      #text(size: 6.5pt)[#milestone.title]
    ]
  ]
}

// Development-only strategic projection. The adjacent TOML file owns the
// snapshot, schedule, blockers, evidence pointers, and review cadence.
#development_only(() => [
  #heading(level: 1, numbering: none)[Development roadmap] <ch:roadmap>
  #metadata(roadmap.meta.reviewed_at.display("[year]-[month]-[day]")) <roadmap-review-date>
  #metadata(roadmap.meta.current_milestone) <roadmap-current-milestone>

  This page is the compact strategic view of thesis development. It is omitted
  from submission output. Scientific claims remain owned by the active thesis;
  executable behavior and measurements remain owned by source, tests,
  configuration, and immutable evidence artifacts.

  #thesis_status(
    implementation: "partial",
    evidence: "pending",
    source: [`docs/typst/thesis/development/roadmap.toml`; active thesis, package, test, configuration, and evidence owners],
    gate: [Close #roadmap.meta.current_milestone before confirmatory policy claims.],
  )[
    Reviewed #roadmap.meta.reviewed_at.display("[day padding:none] [month repr:short] [year]");
    refresh due #roadmap.meta.review_due.display("[day padding:none] [month repr:short] [year]").
    Target: reproducible full-draft freeze by
    #roadmap.meta.complete_by.display("[day padding:none] [month repr:long] [year]"),
    followed by a safety buffer until submission on
    #roadmap.meta.submission_date.display("[day padding:none] [month repr:long] [year]").
  ]

  #metadata("legacy-roadmap-outcome-anchor") <outcome>
  #heading(level: 2, numbering: none)[TL;DR] <ssec:roadmap-snapshot>
  #grid(
    columns: (1fr, 1fr),
    gutter: 6pt,
    row-gutter: 6pt,
    ..roadmap.snapshot.map(snapshot-card),
  )

  #block(breakable: false)[
    #heading(level: 2, numbering: none)[Critical path] <ssec:critical-path>
    The strategic dependency is evidence-first: close the substrate, establish
    paired baseline headroom, evaluate the learned value model, synthesize the
    claims, and freeze the full draft. The December-to-January interval is a
    safety buffer, not planned scientific work.

    #let critical = roadmap.milestones.slice(1, 6)
    #let gate-cells = ()
    #for (index, milestone) in critical.enumerate() {
      gate-cells.push(gate-card(milestone))
      if index < critical.len() - 1 {
        gate-cells.push(text(size: 9pt, fill: gray)[→])
      }
    }
    #figure(
      grid(
        columns: (1fr, auto, 1fr, auto, 1fr, auto, 1fr, auto, 1fr),
        gutter: 3pt,
        align: center + horizon,
        ..gate-cells,
      ),
      caption: [Critical development gates from experiment substrate to the #roadmap.meta.complete_by.display("[day padding:none] [month repr:long] [year]") full-draft freeze.],
    ) <fig:roadmap-critical-path>
  ]

  #heading(level: 2, numbering: none)[Milestones] <ssec:milestones>
  #figure(
    development-table(
      columns: (.45fr, 1.35fr, 1.05fr, .8fr, 2.35fr),
      header: ([*ID*], [*Phase*], [*Dates*], [*State*], [*Exit gate*]),
      rows: roadmap.milestones.map(milestone => (
        [#milestone.id],
        [#milestone.title],
        [#milestone.start.display("[day padding:none] [month repr:short]")–#milestone.end.display("[day padding:none] [month repr:short] [year]")],
        [#text(fill: milestone-colours.at(milestone.status), weight: 700)[#milestone-labels.at(milestone.status)]],
        [#milestone.gate],
      )).flatten(),
      text-size: 7.5pt,
    ),
    caption: [Evidence-gated schedule from the completed pilot infrastructure to submission. Dependencies are checked against the adjacent roadmap data.],
  ) <tab:roadmap-milestones>

  #metadata("legacy-roadmap-risks-anchor") <risks>
  #metadata("legacy-roadmap-issues-anchor") <issues-and-blockers>
  #heading(level: 2, numbering: none)[Blockers] <ssec:roadmap-blockers>
  #for blocker in roadmap.blockers [
    - *#blocker.id — #blocker.title* (affects #blocker.affects.join(", ")): #blocker.body
  ]
  The primary evidence pointers remain beside each record in `roadmap.toml`;
  the roadmap contract checks their existence, while scientific review decides
  whether they are sufficient for promotion.

  #metadata("legacy-roadmap-ablations-anchor") <ablations>
  #metadata("legacy-roadmap-priorities-anchor") <priorities>
  #heading(level: 2, numbering: none)[Promotion queue] <ssec:promotion-queue>
  #for entry in roadmap.promotions {
    promotion_entry(
      entry.summary,
      source: entry.source,
      target-section: entry.target_section,
      gate: entry.gate,
      disposition: entry.disposition,
    )
  }

  #heading(level: 2, numbering: none)[Maintenance contract] <ssec:roadmap-maintenance>
  `roadmap.toml` is the single owner for the snapshot, dates, states,
  dependencies, blockers, release checks, and evidence pointers rendered above. Update it at
  least every #roadmap.meta.review_cadence_days days and whenever a gate changes
  state. `make thesis-roadmap-contract` rejects stale review dates, broken
  dependencies, missing local evidence pointers, divergence from the thesis
  submission date, or references to the retired M1 snapshot. Internal trackers
  and hosted issue state may inform a refresh but are not imported as public
  thesis truth.

  The native table, cards, and critical-path strip are deliberately sufficient:
  they show exact milestones and the consequential dependency chain without a
  second diagram data model. A date-dense Gantt can be reconsidered only if this
  compact projection no longer answers the planning question.

  #heading(level: 2, numbering: none)[HM/FK07 release gate] <ssec:release-gate>
  #block[
    #set text(size: 9pt)
    These checks are human-owned and apply to the exact final candidate and the
    author's authenticated records; the repository cannot satisfy them by itself.
    #for check in roadmap.release_checks [
      - *#check.id — #check.title:* #check.body
    ]

    Official baseline checked
    #roadmap.release_baseline.checked_at.display("[day padding:none] [month repr:long] [year]"):
    #for (index, source) in roadmap.release_sources.enumerate() {
      link(source.url)[#source.title]
      if index < roadmap.release_sources.len() - 1 { [, ] } else { [.] }
    }
    #roadmap.release_baseline.recheck
  ]

  #heading(level: 2, numbering: none)[Freeze and submission] <ssec:freeze>
  By #roadmap.meta.complete_by.display("[day padding:none] [month repr:long] [year]"),
  the full draft, experiment registry, configurations, figures, and release
  checks must be reproducible and free of unresolved placeholders. The interval
  from #roadmap.milestones.last().start.display("[day padding:none] [month repr:long]")
  to #roadmap.meta.submission_date.display("[day padding:none] [month repr:long] [year]")
  is reserved for advisor feedback, formal HM/FK07 checks, final upload, and
  recovery from unexpected defects. Only the authenticated submission receipt
  closes the final gate.
])
