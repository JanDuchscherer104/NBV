---
id: 2026-06-22_readme_current_source_links_refresh
date: 2026-06-22
title: "README current source links refresh"
status: done
topics: [README, docs, thesis, source-order]
confidence: high
canonical_updates_needed: []
---

## Task
Refresh the top-level `README.md` as a concise source map for current
ARIA-NBV thesis and documentation surfaces, including the active Typst thesis
entry point, the 2026-05-22 advisor deck, and important Quarto indexes.

## Method
Read root and docs guidance, source-order rules, current Quarto navigation,
thesis roadmap/questions, and active Typst sources. Kept the README as a
gateway page instead of duplicating roadmap, setup, or downloader details.

## Findings
Updated `README.md` to point at `docs/index.qmd`, `docs/_quarto.yml`,
`docs/contents/thesis/roadmap.qmd`, `docs/contents/thesis/questions.qmd`,
`docs/contents/thesis/m1_contract_report.qmd`,
`docs/contents/literature/index.qmd`, key theory pages,
`docs/typst/thesis/main.typ`,
`docs/typst/thesis/advisor_meeting_2026_05_22.typ`,
`docs/reference/index.qmd`, `SETUP.md`, and `docs/contents/setup.qmd`.
Pruned duplicated offline/downloader prose and kept advisor meeting material
explicitly historical/provenance-only.

## Verification
Local link target existence check passed for all added repo-relative links.
`git diff --check` and `make qmd-frontmatter-check` passed. `make
check-agent-memory` was run and failed on pre-existing tracked `.omx/**`
runtime-state files; no README or debrief-specific validation errors were
reported before that repository-wide blocker.

## Canonical State Impact
None. This was a public README navigation refresh; no canonical state files
needed updates.
