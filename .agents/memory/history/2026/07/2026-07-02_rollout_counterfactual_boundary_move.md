---
id: 2026-07-02_rollout_counterfactual_boundary_move
date: 2026-07-02
title: "Rollout Counterfactual Boundary Move"
status: done
topics: [rollouts, pose-generation, docs, package-boundary]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/counterfactuals.py
  - aria_nbv/aria_nbv/rollouts/target_counterfactuals.py
  - aria_nbv/aria_nbv/pose_generation/__init__.py
  - aria_nbv/aria_nbv/rollouts/__init__.py
  - aria_nbv/aria_nbv/rollouts/AGENTS.md
---

## Task

Moved counterfactual transition replay and target-cropped oracle rollout
scoring out of `aria_nbv.pose_generation` and into `aria_nbv.rollouts` on the
PR15-based `codex/pre-pr15-rollout-boundary` branch. Candidate-table sampling,
validation, orientation, and provenance remain under `aria_nbv.pose_generation`.

## Outputs

- `pose_generation/counterfactuals.py` moved to `rollouts/counterfactuals.py`.
- `pose_generation/target_counterfactuals.py` moved to
  `rollouts/target_counterfactuals.py`.
- `tests/pose_generation/test_counterfactuals.py` moved to
  `tests/rollouts/test_counterfactuals.py`.
- Imports, rollout public exports, API docs navigation, Typst thesis references,
  glossary artifacts, and active agents-db references were updated to the new
  rollout-owned paths.
- `rollouts/AGENTS.md` now states that rollouts own counterfactual transition
  replay and target-aware oracle rollout scorers; pose generation owns only
  finite candidate tables.

## Verification

- `ruff format --check` and `ruff check` passed on touched Python files using
  the main checkout venv tools against this clean worktree.
- `python3 scripts/glossary_build.py all` regenerated glossary artifacts, and
  `python3 scripts/glossary_build.py validate` passed.
- `make agents-db AGENTS_ARGS='validate'` and `make agents-db` passed.
- Import smoke passed for `aria_nbv.rollouts`,
  `aria_nbv.rollouts.counterfactuals`,
  `aria_nbv.rollouts.target_counterfactuals`, `aria_nbv.pose_generation`,
  `aria_nbv.rl`, and `aria_nbv.app.panels.counterfactual_rollouts`.
- Targeted pytest command passed 172 tests and failed one out-of-scope
  PR15-base contract: `tests/data_handling/test_public_api_contract.py` reports
  `vin/scorer_context.py: data_handling._raw`. That import is present in
  `codex/vin-cleanup-pr15-integration` and was not modified because VIN
  implementation is out of scope for this package-boundary move.

## Notes

`uv run` could not execute checks in this clean worktree because
`external/efm3d` is configured as an editable source but has no `pyproject.toml`
or `setup.py`. Validation therefore used the existing main-checkout venv
tooling with `PYTHONPATH` pointed at the clean worktree source.
