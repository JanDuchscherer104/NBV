---
id: 2026-08-28_candidate_support_and_motion_feasibility_foundations
date: 2026-08-28
title: "Candidate Support and Motion Feasibility Foundations"
status: done
topics: [thesis, academic-writing, literature, typst, candidate-generation]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/02-foundations/
  - docs/typst/thesis/main.pdf
  - scripts/tests/test_thesis_literature_provenance.py
codex_thread: codex://threads/01a04842-7454-7353-9a6b-f59cc99302b5
repo_object_format: sha1
repo_head: 363357746983fdb819b7a1a0103de15f0c7a8e79
repo_branch: "codex/thesis-candidate-support-feasibility"
worktree_kind: linked
---

## Task
Integrate candidate-view support and motion-feasibility foundations into Chapter 2 without promoting robot-specific proposal geometry to a human-motion prior.

## Method
Checked the active Chapter 2 contract and local primary-source TeX for PB-NBV, Hestia, Next Best Sense, and Project Aria; realized the accepted argument in Typst; rendered the affected pages; and sent the frozen candidate through independent scientific review.

## Findings
- Added `02-03-candidate-support-and-motion-feasibility.typ` between view utility and finite-horizon value learning.
- Distinguished proposal support, endpoint admission, transition feasibility, and wearable-motion plausibility.
- Bound target-relative orbiting to proposal geometry rather than a claim about natural human movement.
- Aligned the new distinction with the canonical candidate table `cal(Q)_t` and valid-row action set `cal(A)(s_t)`.
- Extended the Chapter 2 synthesis table and provenance-test inventory to cover candidate support and feasibility.

## Commits
- [363357746983fdb819b7a1a0103de15f0c7a8e79](https://github.com/JanDuchscherer104/ARIA-NBV/commit/363357746983fdb819b7a1a0103de15f0c7a8e79)

## Verification
- `make thesis-literature-provenance`: pass, 31 tests.
- `make typst-authoring-contract`: pass, 21 tests.
- `make thesis-marker-contract thesis-pdf-ci check-agent-memory`: pass.
- `make thesis-pdf`: pass; affected Chapter 2 pages rendered and visually inspected.
- Independent scientific review: initial P2 notation finding repaired; exact repaired hashes re-reviewed clear.
- `git diff --check`: pass.

## Canonical Owner Impact
Chapter 2 now owns the conceptual distinction between candidate proposal support, hard feasibility admission, and view ranking. Method and data-generation chapters remain the owners of concrete candidate families, masks, generation rules, and validation thresholds.
