---
id: 2026-08-26_thesis_introduction_narrative_and_rq_rewrite
date: 2026-08-26
title: "Thesis introduction narrative and research-question rewrite"
status: done
topics: [thesis, introduction, academic-writing, scientific-review, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/main.typ
  - docs/typst/thesis/sections/01-introduction.typ
  - docs/typst/thesis/sections/01-research-questions.typ
codex_thread: codex://threads/01a03f66-55b2-7932-9ec8-4dc817e89783
repo_object_format: sha1
repo_head: 95f574fdb6f89c4107ad8865629bde5949322a9f
repo_branch: "main"
worktree_kind: primary
---

## Task
Critically review and fully revise the thesis introduction, all `01-*` thesis
sections, and both abstracts using the complete thesis structure and adjacent
primary literature.

## Method
Mapped the active thesis dependency chain and evidence status, checked adjacent
quality-driven, target-aware, egocentric, and sequential NBV sources, froze an
independent scientific review before authoring, and realized the accepted
content in the canonical Typst owners. A second independent scientific review
then rechecked the revised candidate against the original blocking findings.
A follow-up simplification pass removed repeated protocol and status prose,
followed by a fresh independent review of the reduced candidate.

## Findings
- The introduction must establish the active-perception problem, the conflict
  between coverage and target-specific reconstruction quality, the bounded
  finite-candidate research object, the actor/oracle information boundary, the
  contribution classes and their evidence status, and the chapter-level proof
  sequence.
- The previous text conflated current and planned actor inputs, misdescribed the
  VIN-NBV metric adaptation, omitted an explicit contribution statement and
  chapter roadmap, and under-specified the RQ estimands and decision rules.
- The revised chapter distinguishes implemented, planned, conditional, and
  deferred scope; treats RQ1--RQ4 as the core bounded experiment; and retains
  RQ5--RQ6 as conditional or deferred extensions.
- RQ2 remains prospective because its meaningful-effect threshold, uncertainty
  procedure, and learned-recovery fraction are not yet frozen. The revision
  makes that experiment-design gate explicit rather than inventing a value.
- Both abstracts now state problem, gap, method, intended evidence, current
  status, limitations, and non-claims without implying policy superiority.
- The simplification pass reduced the two `01-*` sources from about 2,350 to
  about 1,240 rendered-source words, removed the repeated research-to-evidence
  table, and retained every formal RQ, displayed equation, and scientific gate.

## Commits
none

## Verification
- Strict targeted Typst hygiene passed for the three changed source owners.
- The thesis compiled successfully to a 141-page PDF; the Introduction occupies
  five pages instead of nine.
- Typst authoring and thesis marker contract checks passed.
- Visual QA covered both abstract pages and every Introduction page.
- A fresh independent review found no P0/P1 blocker after simplification.
- Targeted `git diff --check` passed.

## Canonical Owner Impact
The active thesis introduction, research questions, and bilingual abstracts now
own the revised narrative, claim boundaries, contribution statement, evidence
logic, and chapter roadmap. No executable behavior or empirical result changed.
