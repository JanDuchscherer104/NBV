---
id: 2026-08-28_candidate_support_thesis_integration
date: 2026-08-28
title: "Candidate support thesis integration"
status: done
topics: [candidate-generation, evidence, streamlit, thesis, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/candidate_benchmark.py
  - aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py
  - aria_nbv/aria_nbv/rollouts/inspection.py
  - docs/contents/evidence/candidate_target_orbit_mvp
  - docs/typst/shared/equations/metrics.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation
  - docs/literature/sources.jsonl
  - docs/references.bib
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: f2968096c467107e84084c25eaf92e5bc8f97959
repo_branch: "codex/thesis-candidate-support-integration"
worktree_kind: linked
---

## Task
Integrate the reviewed candidate-generation diagnostics and real-data target-orbit pilot into the thesis while preserving portable evidence, inspection plots, and the production seminar-jitter contract.

## Method
Stacked the work on the target-orbit MVP branch, joined benchmark rows to the canonical proposal-support geometry reducer, added target-aligned plotting and an opt-in camera-forward arrow overlay, froze a two-scene CUDA evidence bundle, and defined state--scene--cohort aggregation in shared Typst notation. Independent code and scientific reviews were iterated to zero actionable P0--P2 findings.

## Findings
- `aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py` now owns the ground-plane, 3D, family-survival, and bounded/uncapped jitter plots used by Streamlit.
- `aria_nbv/aria_nbv/rollouts/candidate_benchmark.py` and `inspection.py` preserve target-aligned candidate geometry, per-candidate bounded-jitter provenance, and projected camera optical axes.
- `docs/contents/evidence/candidate_target_orbit_mvp/` is a hash-bound portable bundle with explicit expected states, reduced rows, reproduction scripts, HTML/PNG plots, summary scalars, and undefined-state/scene counts.
- `docs/typst/shared/equations/metrics.typ` and Chapter 3 define configured-family denominators, eligible state/scene sets, side balance, circular orbit span, projection, finite-label oracle opportunity, and per-state jitter QC.
- The static thesis plot stays uncluttered; Streamlit and the evidence script can optionally render fixed-length ground-projected arrows for valid cameras' `+Z` optical axes without overwriting canonical artifacts.
- OA-NBV, Where to Look Next, and Aria Digital Twin were registered in both literature owners for the proposal/feasibility and empirical-motion calibration discussion.

## Commits
- https://github.com/JanDuchscherer104/ARIA-NBV/commit/f2968096c467107e84084c25eaf92e5bc8f97959

## Verification
- `pytest` over the candidate benchmark, inspection, and Streamlit panel contracts: 143 passed.
- Ruff format/check and mypy over the changed rollout owners: passed.
- `make glossary typst-authoring-contract thesis-report-data-contract thesis-marker-contract thesis-pdf-ci thesis-literature-provenance`: passed.
- The hash-bound portable-evidence test and empty-profile denominator regression: passed.
- Development thesis pages 40--42 were rendered and inspected; the candidate-support figure is legible and correctly anchored.
- Independent final scientific and code reviews reported no actionable P0--P2 findings.

## Canonical Owner Impact
Current truth changed in the rollout inspection/benchmark/plotting owners, the candidate-target-orbit evidence bundle, shared metric equations, Chapters 3/5/6 and the appendix, report-data contracts, and both literature registries. The production candidate mixture and its nonzero seminar-jitter invariant were not changed.
