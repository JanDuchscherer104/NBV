---
id: 2026-08-26_pr126_selection_lineage_and_sequence_color_review_fixes
date: 2026-08-26
title: "PR126 selection lineage and sequence color review fixes"
status: done
topics: [candidate-generation, replay, zarr, streamlit]
confidence: high
canonical_updates_needed: []
touched_owner_paths: []
codex_thread: codex://threads/01a033a6-100a-73d2-83bb-4a4153903cc4
repo_object_format: sha1
repo_head: 72316825fdc7d7a730de82758df520274cf2c9e9
repo_branch: "codex/g001-pr126-review-fixes"
worktree_kind: linked
---

## Task
Resolve PR #126 review findings while retaining state-keyed replay lineage and the
existing bounded/uncapped jitter visualization behavior.

## Method
Worked in an isolated linked worktree, added the derived state selection seed to
all selection records, bound valid and invalid proposal-order traces to one
Plotly coloraxis, and added direct/replay/Zarr/plot regressions. Rebased the
focused change onto the live `origin/main` before final verification.

## Findings
`aria_nbv/aria_nbv/rollouts/replay/engine.py` now carries the derived selection
seed through stochastic and one-hot selection records, allowing the existing
Zarr step table to round-trip the lineage. `aria_nbv/aria_nbv/pose_generation/
plotting.py` uses one sequence color range for valid and invalid traces while
preserving the existing uncapped spherical axes and bounded envelope behavior.
Focused tests cover direct replay records, Zarr persistence, and Plotly traces.

## Commits
- [72316825fdc7d7a730de82758df520274cf2c9e9](https://github.com/JanDuchscherer104/ARIA-NBV/commit/72316825fdc7d7a730de82758df520274cf2c9e9)

## Candidate Owner Intent
<!-- Omit this section unless the agent-behavior candidate-intent branch applies. -->
- Statement: <precise reusable preference>
- Evidence: <direct instruction or bounded recurring evidence>
- Scope and target owner: <scope and exact owner path>
- Status: proposed for current-user review

## Verification
- Ruff format/check passed for all five changed Python/test owners.
- `pytest -q tests/pose_generation/test_plotting_helpers.py
  tests/rollouts/test_counterfactuals.py tests/rollouts/test_dataset_writer.py`
  passed: 86 tests.
- `git diff --check` passed after the rebase onto `origin/main`.

## Canonical Owner Impact
Replay selection lineage and proposal-sequence visualization owners plus their
focused tests were updated. Production seminar jitter, bounded envelopes, and
uncapped spherical support semantics were preserved.
