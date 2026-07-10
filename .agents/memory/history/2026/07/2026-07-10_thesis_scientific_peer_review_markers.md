---
id: 2026-07-10_thesis_scientific_peer_review_markers
date: 2026-07-10
title: "Thesis Scientific Peer Review and Submission Markers"
status: done
topics: [thesis, typst, peer-review, literature, scientific-writing]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/draft_markers.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/sections/
  - docs/typst/thesis/appendix/index.typ
artifacts:
  - .omx/goals/autoresearch/thesis-scientific-peer-review/review-report.md
assumptions:
  - The active Typst thesis may retain marked development-diary material, but the submission build must remove or rewrite every item labeled with prune_todo.
---

## Task

Peer-review the active thesis against general scientific-writing standards, the thesis roadmap/questions, and repo literature reviews; identify incorrect, unsupported, boilerplate, AI-slop, and non-final material; and annotate it without deleting the integrated research diary.

## Method

Mapped the active include graph and marker macros, queried Graphify for thesis/literature relationships, ran three bounded read-only section/literature review lanes, inspected the active Typst and QMD owners, and added an explicit `prune_todo` marker plus typed conflict, validation, implementation, research, and question markers beside affected prose.

## Findings and outputs

The conceptual core is sound around actor/oracle separation, hard invalidity masks, geometric candidate-set contracts, reward/endpoint separation, and replay provenance. Submission blockers are the proposal abstract, scaffold results/discussion/conclusion, target-task provenance ambiguity, unvalidated target-RRI density/tessellation assumptions, acquisition-horizon versus planning-depth conflict, planned architectures written as Method, citation-role errors, and internal migration/operation ledgers in the main narrative.

The review added 35 typed markers, including 15 submission-pruning markers, across the active thesis. No scientific content was deleted. The shared marker wrapper was made non-breakable after visual QA caught a page-split label. The ignored autoresearch artifact contains the severity-ranked review and complete section coverage.

## Verification

- `typst compile typst/thesis/main.typ /tmp/aria-thesis-peer-review.pdf --root . --input aria-wip-links=false --input aria-code-ref=<current-sha>` passed.
- The rendered PDF has 117 A4 pages; representative abstract, introduction, related-work, target/oracle, candidate, replay-diagnostic, value-model, policy-comparison, and appendix pages were visually inspected.
- `git diff --check -- docs/typst/thesis` passed.

## Canonical state impact

No research direction or implementation truth changed. The edits expose finalization obligations next to existing thesis prose and preserve roadmap/questions as the current direction owners.
