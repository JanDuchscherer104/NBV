---
id: 2026-09-01_pr190_method_design_space_and_canonical_glossary_repair
date: 2026-09-01
title: "PR190 method design space and canonical glossary repair"
status: done
topics: [thesis, method, glossary, notation, scientific-markers]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/04-method
  - docs/typst/shared/glossary.typ
  - docs/typst/shared/equations.typ
  - docs/typst/shared/symbols.typ
  - docs/typst/thesis/draft_markers.typ
  - scripts/glossary_build.py
codex_thread: codex://threads/01a057bd-546e-7e52-b5e8-c21124664bc2
repo_object_format: sha1
repo_head: efad7e09ef91ea6264f00cf1ee9dae7054453783
repo_branch: "codex/pr190-stack-repair"
worktree_kind: linked
---

## Task
Restore the conceptually valid Method design space without conflating implementation, selection, and evidence, improve canonical notation use, rank scientific-core architecture/data TODOs, and remove duplicated glossary semantics from generated Typst adapters.

## Method
Compared the PR #190 candidate against its parent and implementation owners, restored bounded alternatives with explicit scientific roles, extended the existing draft-marker contract with orthogonal priority/readiness metadata, moved all glossary semantics to the shared canonical owner, regenerated projections, compiled the thesis, inspected affected pages, and obtained an independent scientific closure review.

## Findings
- `docs/typst/thesis/sections/04-method/` now distinguishes selected realization, matched controls, scientific target requirements, contingent alternatives, and exploratory ideas independently from implementation and evidence maturity.
- `docs/typst/shared/glossary.typ`, `docs/typst/shared/equations.typ`, and `docs/typst/shared/symbols.typ` own the shared CF0, S0/S1/S2, selected-history, and scalar-horizon semantics; the former thesis-local glossary override was removed.
- `docs/typst/thesis/draft_markers.typ` extends the existing marker system with P0-P3 scientific-core priorities and independent ready/blocked/contingent readiness for architecture and data tasks.
- `scripts/glossary_build.py` now emits canonical-backed compatibility aliases rather than a second Typst glossary or copied definitions; generated notation contains one consumer projection rather than duplicate map/list definitions.
- An independent scientific review initially found stale CF0/Q metadata and missing design-space provenance. The canonical metadata, public projections, source locators, and semantic regression were repaired before approval.

## Commits
- [efad7e09ef91ea6264f00cf1ee9dae7054453783](https://github.com/JanDuchscherer104/ARIA-NBV/commit/efad7e09ef91ea6264f00cf1ee9dae7054453783) — restore Method design space, canonical shared glossary/notation, ranked scientific-core markers, and generator regressions.

## Verification
- `make glossary` — passed; 58 terms, 117 symbols, and 122 equations; a second run was byte-idempotent across all generated projections.
- `aria_nbv/.venv/bin/python -m pytest scripts/tests/test_glossary_build.py -q` — 6 passed.
- `aria_nbv/.venv/bin/python scripts/tests/test_thesis_marker_contract.py` — passed, including invalid priority/domain/readiness/blocker fixtures.
- `make typst-authoring-contract` — 21 passed.
- `make thesis-literature-provenance` — 31 passed.
- `make thesis-pdf-ci` and `make thesis-pdf` — passed; the tracked thesis is 140 A4 pages.
- Render inspection of the state-realization, interaction-ladder, decoder-design, and scientific-core marker pages found no clipping or overlap.
- Independent closure review of candidate digest `d77719352f0665ac21fa473ddbae28ddb4a47253647b2a65e5a8d4904b1721ac` — clear, zero findings.
- `git diff --check` — passed.

## Canonical Owner Impact
- Shared glossary semantics remain in `docs/typst/shared/glossary.typ`; generated YAML, Lua, JSONL, QMD, and Typst files are projections only.
- Shared notation/equation semantics remain in `docs/typst/shared/symbols.typ`, `docs/typst/shared/equations.typ`, and their domain modules.
- Submission-facing Method semantics remain in `docs/typst/thesis/sections/04-method/`; development alternatives remain explicitly non-submission-facing.
- Scientific-core TODO rank semantics extend the existing `docs/typst/thesis/draft_markers.typ` owner and do not introduce a second backlog.
