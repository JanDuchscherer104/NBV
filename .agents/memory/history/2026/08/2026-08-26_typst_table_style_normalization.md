---
id: 2026-08-26_typst_table_style_normalization
date: 2026-08-26
title: "Typst table style normalization"
status: done
topics: [thesis, typst, tables, reporting, visual-qa]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - Makefile
  - docs/typst/seminar_paper
  - docs/typst/seminar_slides/slides_4.typ
  - docs/typst/shared/notation.typ
  - docs/typst/shared/slide-template.typ
  - docs/typst/shared/tables.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/experiment_data.typ
  - docs/typst/thesis/sections
  - docs/typst/thesis/appendix/index.typ
  - docs/typst/thesis/development/m1-contract-report.typ
  - docs/typst/thesis/tests
  - docs/typst/thesis_slides/advisor_meeting_2026_05_22.typ
  - scripts/tests/test_typst_authoring_hygiene.py
  - scripts/tests/test_typst_report_data_contract.py
codex_thread: codex://threads/01a03f70-b1cd-72e2-963a-ee84912ecf95
repo_object_format: sha1
repo_head: 95f574fdb6f89c4107ad8865629bde5949322a9f
repo_branch: "main"
worktree_kind: primary
---

## Task
Normalize every active authored scientific table through one shared Typst style
owner, add a multi-index gallery, and preserve the presentation-neutral report
data seam shared with the Streamlit application.

## Method
Locked a derived active-table inventory, introduced a shallow Booktabs-based
presentation API, migrated 29 publication tables, one development table, and 12
presentation tables,
and added exact multi-store fact lookup plus positive and negative Typst data
fixtures. Synthetic gallery patterns were compiled and reviewed at 300 PPI in
color and grayscale. Independent code and architecture reviews challenged the
final integrated source after focused and full documentation builds.

## Findings
- Native Typst tables with Booktabs 0.0.4 support the required hierarchy; no
  replacement table package or generic table DSL is needed.
- `docs/typst/shared/tables.typ` is the sole presentation owner for palette,
  spacing, rules, semantic headers, and group/index cell styling. Captions,
  labels, columns, data selection, and interpretation remain at call sites.
- Seminar-paper, seminar-slide, advisor-slide, and printed-notation tables use
  the same owner through publication- or presentation-sized constructors.
  Structural title-page layout, archived sources, and package manuals remain
  explicit non-scientific or historical/reference exclusions.
- The gallery proves profile, target-stratum, policy, metric-family, measure,
  parameter-family, and key indices together with grouped numeric columns.
- Results consume ordinary typed report rows and keep estimates, intervals,
  units, and denominators separate. Typst does not read Streamlit state or raw
  rollout stores and does not define another report schema.
- Store-qualified named quantities fail closed unless exactly one matching
  `(store_id, key)` row exists; the negative fixtures check the intended error.
- A concurrent thesis rewrite removed the research-to-evidence table during
  validation. Reapplying only that table to the newest prose restored the
  plan-required 17-table inventory without reverting the concurrent rewrite.

## Commits
none

## Verification
- Typst authoring hygiene passed 21 tests and reports 29 publication tables,
  one development table, and 12 presentation tables with authoritative
  shared-owner imports.
- Report-data smoke, missing lookup, and duplicate lookup contracts passed.
- Four focused reporting parity, byte-stability, schema, and serialization tests
  passed without changing the Python reporting schema.
- Thesis PDF, seminar paper, both slide decks, the orphan seminar-section smoke
  fixture, marker contract, gallery target, and full `docs-render-core` passed.
- Fresh 300-PPI color and grayscale QA passed for every affected thesis table
  page, every seminar-paper table page, both slide decks, the orphan section,
  and the final four-pattern gallery.
- Independent code review returned APPROVE; architecture review returned CLEAR.
- The structural title-page source remained byte-identical and the scoped diff
  passed whitespace checks.

## Canonical Owner Impact
Active authored scientific-table presentation across thesis, paper, slide, and
notation surfaces now has one shared Typst owner and an executable
provenance/inventory contract. Scientific semantics and report-data ownership
remain with their existing thesis and Python owners.
