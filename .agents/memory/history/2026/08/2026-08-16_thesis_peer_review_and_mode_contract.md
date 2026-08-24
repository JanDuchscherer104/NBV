---
id: 2026-08-16_thesis_peer_review_and_mode_contract
date: 2026-08-16
title: "Thesis Peer Review And Submission Mode Contract"
status: done
topics: [thesis, typst, peer-review, citations, graphify, scientific-writing]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/draft_markers.typ
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/sections
  - .agents/skills/typst-authoring
---

## Task

Review every active thesis section for scientific prose, narrative continuity,
evidence, citation provenance, development/submission ownership, and alignment
with exact code and literature owners. Use freshness-gated Graphify for
navigation, mark concrete manuscript issues, and distill missing authoring
invariants.

## Method

Inspected the active Typst include graph, development render, submission gates,
bibliography and local TeX sources, representative implementation owners, and
Graphify projection/paths. A research agent surveyed primary and official ML/CS
writing and reproducibility guidance. Graphify was treated as structurally stale
derived navigation and every material lead was checked against exact sources.

## Findings

The draft has a strong actor/oracle, validity, missingness, and evidence-gating
spine, but it is currently a development dossier rather than one frozen and
evaluated scientific method. The largest blockers are missing confirmatory
policy evidence, unresolved method/horizon alternatives, under-specified
empirical inference, catalogue-like related work, internal implementation
terminology, and result/discussion/conclusion chapters that remain conditional.

Claim-level literature provenance is now specified as non-rendered structured
comments beside the supported paragraph or object. Unguarded content is
submission-facing; development-only content uses an explicit wrapper; TODO and
editorial status constructs block submission compilation. A narrow empirical
reporting and reproducibility reference was added to the Typst authoring skill.

## Verification

Development Typst compilation and representative PNG inspection passed.
Submission stopped at the intended explicit-evidence gate and, with a temporary
test-only evidence-role fixture, at the intended unresolved-marker gate. Strict
Typst hygiene, skill validation, `make check-agent-memory`, scaffold audit and
self-tests, all 42 Graphify projection tests, projection `--check`, and
`git diff --check` passed. Scaffold audit retained 13 existing warnings and no
errors. The semantic Graphify graph was not refreshed or promoted to authority.

## Canonical-State Impact

Current truth was updated directly in `draft_markers.typ`, `main.typ`, and the
repo-local `typst-authoring` skill references. No additional canonical state
document remains to be updated.
