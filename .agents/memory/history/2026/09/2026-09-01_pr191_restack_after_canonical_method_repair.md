---
id: 2026-09-01_pr191_restack_after_canonical_method_repair
date: 2026-09-01
title: "PR191 restack after canonical Method repair"
status: done
topics: [thesis, evidence-gates, discussion, restack]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/sections/07-discussion.typ
  - scripts/tests/test_typst_authoring_hygiene.py
codex_thread: codex://threads/01a057bd-546e-7e52-b5e8-c21124664bc2
repo_object_format: sha1
repo_head: 072a027196404c32b4ac8f633c7cb118917c73b0
repo_branch: "codex/pr191-stack-repair"
worktree_kind: linked
---

## Task
Restack PR #191 onto the repaired PR #190 head without losing either the evidence-gate interpretation or the newly restored Method design space and ranked scientific-core follow-up contract.

## Method
Rebased the complete PR #191 commit range onto PR #190 head `d951c2ae4a8512d442ae26efa96d29aa40c11e13`, regenerated every binary thesis-PDF conflict, merged the Discussion semantically, and ran exact-head documentation, provenance, marker, projection, PDF, and memory checks.

## Findings
- `docs/typst/thesis/sections/07-discussion.typ` retains PR #191's fail-closed diagnostic-admissibility interpretation and adds PR #190's evidence-conditioned architecture bridges plus the structured P2 scientific-core TODO.
- The integrated branch contains 31 active publication tables: PR #191 replaces more parent tables than it adds, so `scripts/tests/test_typst_authoring_hygiene.py` now records the derived integrated count rather than either historical layer count.
- Binary PDF conflicts were resolved only by rebuilding from the merged Typst source.

## Commits
- [072a027196404c32b4ac8f633c7cb118917c73b0](https://github.com/JanDuchscherer104/ARIA-NBV/commit/072a027196404c32b4ac8f633c7cb118917c73b0) — bind the integrated active-table inventory after restacking.

## Verification
- Exact first-child parent is PR #190 head `d951c2ae4a8512d442ae26efa96d29aa40c11e13`.
- `make graphify-projection-live-check` — passed across 626 Markdown files.
- `make typst-authoring-contract` — 21 passed.
- `make thesis-literature-provenance` — 31 passed.
- `make thesis-marker-contract`, `make thesis-pdf-ci`, and `make check-agent-memory` — passed.
- `git diff --check` — passed.

## Canonical Owner Impact
- PR #191 remains the Results/evidence-gate layer; it does not redefine the Method contracts owned by PR #190.
- Discussion now explicitly connects failed evidence gates to contingent architecture promotion without treating missing evidence as a negative result.
