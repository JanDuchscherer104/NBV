---
id: 2026-09-01_candidate_evidence_snapshot_and_plot_architecture_pr4a
date: 2026-09-01
title: "Candidate Evidence Snapshot And Plot Architecture PR4a"
status: done
topics: [candidate-generation, rollout-inspection, visualization, architecture]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - aria_nbv/aria_nbv/rollouts/candidate_evidence.py
  - aria_nbv/aria_nbv/rollouts/candidate_plotting.py
  - aria_nbv/aria_nbv/rollouts/candidate_support_plotting.py
  - aria_nbv/aria_nbv/rollouts/read_model.py
  - docs/contents/evidence/candidate_evidence_snapshot_real_scenes/
codex_thread: codex://threads/01a05903-535c-7c21-8ae7-e7c17079427c
repo_object_format: sha1
repo_head: 6e16f8aa994475ec3ff04151a97f77159e872f9f
repo_branch: "codex/candidate-evidence-plots-pr4a"
worktree_kind: linked
---

## Task
Establish the presentation-free candidate-evidence seam and make live, stored,
and legacy-compatible plots consume one immutable attempted-shell snapshot.

## Method
Added a row-aligned `CandidateEvidenceSnapshot`, explicit live and stored
adapters, one snapshot-only Plotly core, and compatibility wrappers for the
existing benchmark API. Characterization tests froze N/V/A/K, semantic versus
legacy lineage, target-relative frames, admission, jitter, selection, plot
identity, and no-reacquisition behavior. Two factual CUDA pilot rollout states
were captured into reader-free snapshots and deterministic static artifacts.

## Findings
`aria_nbv/aria_nbv/rollouts/candidate_evidence.py` is the canonical immutable
evidence owner. It preserves nonfinite attempted rows with typed unavailability,
keeps old-store omissions explicit, and validates stored selection/projection
alignment before deriving the expansion frame. Plot construction moved to
`aria_nbv/aria_nbv/rollouts/candidate_plotting.py`; legacy benchmark entry
points delegate through the same scientific reducer. The real stores predate
persisted jitter facts, so their jitter artifact explicitly reports
legacy-missing evidence rather than displaying invented zeros.

## Commits
- [6e16f8aa994475ec3ff04151a97f77159e872f9f](https://github.com/JanDuchscherer104/ARIA-NBV/commit/6e16f8aa994475ec3ff04151a97f77159e872f9f)
- [ab104ebcbe770ddce8ffc09a886006b17393759b](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ab104ebcbe770ddce8ffc09a886006b17393759b)

## Verification
- Focused snapshot, read-model, benchmark, and compatibility suite: 90 passed.
- Candidate benchmark Streamlit and wrapper suite: 65 passed.
- Repository-config Ruff on all owned Python files: passed.
- Strict package-config mypy on six source/contract files: passed.
- Real-scene Plotly JSON, HTML, and PNG rebuild: byte-identical across two runs;
  all four PNGs visually inspected after the legibility pass.
- Repo `make ruff-targeted` and `make mypy-targeted` could not resolve the
  linked worktree's absent editable `external/efm3d`; equivalent checks used
  the primary checkout's shared environment with this worktree on `PYTHONPATH`.

## Canonical Owner Impact
Current Python owners, public typing contracts, compatibility tests, and the
durable two-scene evidence bundle were updated. No configuration, generation
algorithm, persistence writer, or thesis claim changed in this workpackage.
