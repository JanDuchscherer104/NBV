---
id: 2026-08-31_strategic_thesis_roadmap_refresh
date: 2026-08-31
title: "Strategic thesis roadmap refresh"
status: done
topics: [thesis, roadmap, typst, planning, verification]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/development/roadmap.toml
  - docs/typst/thesis/development/roadmap.typ
  - docs/typst/thesis/development/m1-contract-report.typ
  - scripts/tests/test_thesis_roadmap_contract.py
  - Makefile
  - docs/AGENTS.md
codex_thread: codex://threads/01a057bd-546e-7e52-b5e8-c21124664bc2
repo_object_format: sha1
repo_head: 90fba10dc7a778f55e3345d0f00db065a1b39032
repo_branch: "codex/thesis-strategic-roadmap"
worktree_kind: linked
---

## Task

Replace the stale seminar-era development view with a compact, evidence-bounded
roadmap through the 2027-01-07 thesis submission and retire the duplicate M1
status owner.

## Method

Inspected committed experiment artifacts, thesis claims and gates, current
hosted issues and pull requests, and upstream Typst diagram packages. Realized
the accepted status model as one TOML owner, a native Typst projection, and a
freshness/schema/chronology contract. An independent architect reviewed the
candidate; all three P2 consistency findings were corrected before commit.

## Findings

- `roadmap.toml` now owns review cadence, snapshot states, milestones,
  dependencies, blockers, promotion gates, and evidence pointers.
- `roadmap.typ` renders a four-card TL;DR, critical path, milestone table,
  blockers, promotion queue, and submission buffer without a package dependency.
- `m1-contract-report.typ` is an unincluded, claim-free compatibility shim; its
  historical anchors remain resolvable without retaining a second status view.
- `test_thesis_roadmap_contract.py` fails on stale review dates, invalid schema
  or chronology, broken evidence pointers, metadata drift, or revived M1 usage.

## Commits

- https://github.com/JanDuchscherer104/ARIA-NBV/commit/90fba10dc7a778f55e3345d0f00db065a1b39032

## Verification

- `make thesis-roadmap-contract`: passed, including negative staleness evidence.
- `make typst-authoring-contract`: 21 tests passed.
- `make thesis-marker-contract`: passed.
- `make thesis-pdf`: passed; roadmap pages 109--112 were visually inspected and
  are legible and unclipped.
- `make thesis-literature-provenance`: 31 tests passed.
- `make check-agent-memory`, Ruff format/check, and `git diff --check`: passed.
- The complete pre-push docs render passed. The separate strict Graphify-state
  hook could not initialize this new worktree because no registered ancestor had
  a query-admissible Graphify snapshot; hosted exact-head CI remains the final
  publication proof.

## Canonical Owner Impact

The TOML file is the single current public roadmap owner. Typst, the Make target,
the contract test, and `docs/AGENTS.md` project or enforce it; no further
canonical update is pending.
