---
id: 2026-09-02_pr_190_scientific_contract_repair
date: 2026-09-02
title: "PR 190 scientific contract repair"
status: done
topics: [thesis, academic-writing, typst, qh, vin, rollouts, rri]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/
  - docs/typst/thesis/sections/05-experimental-design/
  - aria_nbv/aria_nbv/data_handling/
  - aria_nbv/aria_nbv/rollouts/
  - aria_nbv/aria_nbv/rri_metrics/returns.py
touched_owner_paths:
  - docs/typst/thesis/
  - docs/typst/shared/
  - aria_nbv/aria_nbv/data_handling/
  - aria_nbv/aria_nbv/rollouts/
  - aria_nbv/aria_nbv/rri_metrics/returns.py
  - aria_nbv/tests/
codex_thread: codex://threads/01a0625f-02d8-7310-bc98-9c62b8c61df8
repo_object_format: sha1
repo_head: dec62811e0f75e6be55f53c71472e56e105018e2
repo_branch: "review/pr190"
worktree_kind: primary
---

## Task
Repair the explicit scientific, mathematical, provenance, and implementation-contract findings on PR 190.

## Method
Mapped each review finding to its canonical Typst, Python, contract, and test owner; repaired the corresponding definitions and contracts; regenerated notation, evidence projections, and the thesis PDF; then ran focused and owner-level verification.

## Findings
The implementation now preserves actor-visible VIN reference-pose ownership, enforces the V11 offline-store schema, computes the q-train root gain and rollout return through all public seams, and retains RRI diagnostics as optional evidence. The thesis distinguishes learned finite-candidate values from their target, defines introduced symbols at use, bounds Phase-A claims to their deterministic projection, and aligns RQ5 and the experimental interpretation with the implemented contracts.

## Commits
- [995b0841d7c56273c4a5000b5f82356057641e96](https://github.com/JanDuchscherer104/ARIA-NBV/commit/995b0841d7c56273c4a5000b5f82356057641e96) — implementation commit.

## Verification
Passed: targeted pytest suites (201 tests); full owning Python suite (300 tests); Ruff check and format; `make glossary`; `make typst-authoring-contract`; `make thesis-pdf-ci`; `make thesis-pdf`; `make phase-a-thesis-projection`; `make thesis-report-data-contract`; `make thesis-marker-contract`; `make thesis-literature-provenance`; and `git diff --check`.

## Canonical Owner Impact
Updated the owning Typst, generated notation, data-handling, rollout, RRI-return, target-selection, inspection, and regression-test surfaces. The standalone Phase-A projection script is the deterministic evidence producer; its JSON and SVG projections are derived artifacts.
