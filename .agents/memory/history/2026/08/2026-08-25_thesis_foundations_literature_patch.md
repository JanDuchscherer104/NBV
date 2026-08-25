---
id: 2026-08-25_thesis_foundations_literature_patch
date: 2026-08-25
title: "Thesis foundations literature patch"
status: done
topics: [thesis, academic-writing, literature, typst, qh]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/02-foundations/
  - docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ
  - docs/typst/thesis/sections/05-experimental-design/05-02-learning-objective-and-replay-evidence.typ
  - docs/typst/shared/equations/rl.typ
  - docs/typst/shared/symbols/rl.typ
  - docs/references.bib
  - docs/references-qh.bib
  - docs/literature/sources.jsonl
  - scripts/tests/test_thesis_literature_provenance.py
codex_thread: codex://threads/01a03a5c-ff92-7e03-8cd3-fde05269a56f
repo_object_format: sha1
repo_head: 3fb775b9bcaf6bbcd08841203eeb302ecd8ce557
repo_branch: "codex/thesis-foundations-literature-patch"
worktree_kind: primary
---

## Task
Implement the reviewed Foundations, background, and literature patch on current
`main` without importing scorer-stack implementation claims, then publish it as
a reviewable pull request.

## Method
Selected the current-main lane from the accepted plan, acquired exact local
primary sources before writing new claims, replaced the two compressed Chapter
2 owners with five source-grounded sections, synchronized shared notation and
equations, added two original conceptual figures, and expanded the provenance
test across the full chapter. A fresh independent scientific reviewer examined
the exact candidate; blocking and material findings were repaired before the
implementation commit.

## Findings
- `docs/typst/thesis/sections/02-foundations/` now separates view utility,
  target/action support, finite-horizon value theory, egocentric/geometric
  representation, and bounded literature positioning.
- `docs/typst/shared/equations/rl.typ` now defines the optimal finite-support
  continuation estimand, absorbing terminal convention, horizon-specific
  factual support, and support-gated Double-Q successor admission.
- `docs/literature/sources.jsonl` and the bibliography owners now join
  Fixed-Horizon TD, UVFA, the robotics POMDP survey, and invalid-action masking
  to repository-owned primary-source assets.
- `scripts/tests/test_thesis_literature_provenance.py` now fails closed across
  all five Foundations sections rather than one legacy Related Work file.

## Commits
- [3fb775b9bcaf6bbcd08841203eeb302ecd8ce557](https://github.com/JanDuchscherer104/ARIA-NBV/commit/3fb775b9bcaf6bbcd08841203eeb302ecd8ce557) — implementation workpackage

## Verification
- `make glossary` — pass; 56 glossary terms, 93 symbols, and 95 equations.
- `make thesis-literature-provenance` — pass; 31 tests.
- `make typst-authoring-contract` — pass.
- `make thesis-marker-contract` — pass.
- `make thesis-pdf-ci` — pass; 129-page development thesis.
- Standalone Typst compilation for both new figures — pass.
- Rendered-page inspection for Chapter 2 pages 38--44 and affected Method page
  91 — pass; no clipping or illegible table/figure layout.
- Ruff format/check for the changed provenance test and `git diff --check` —
  pass after mechanically normalizing imported-source whitespace.
- Fresh independent scientific review — pass; no blocking or material finding.

## Canonical Owner Impact
Current thesis truth changed in the Chapter 2 section owners and the smallest
dependent Method/Experimental Design passages. Shared notation/equation,
bibliography, literature-manifest, and provenance-test owners were synchronized;
no Python scorer or learner behavior changed.
