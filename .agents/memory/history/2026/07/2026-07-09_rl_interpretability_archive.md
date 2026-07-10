---
id: 2026-07-09_rl_interpretability_archive
date: 2026-07-09
title: "RL And Interpretability Archive"
status: done
topics: [aria-nbv, archive, streamlit, tests]
confidence: high
canonical_updates_needed: []
---

## Task

Archive `aria_nbv.rl` and `aria_nbv.interpretability` out of the active package
surface and remove their Streamlit and test contact points.

## Method

The implementation followed the approved ralplan consensus handoff from
`.omx/plans/ralplan-archive-rl-interpretability-handoff-20260709T100521Z.json`.
Both module directories were moved with `git mv` into
`.agents/archive/aria_nbv/aria_nbv/`, while active app config, navigation,
panel dispatcher exports, package dependencies, and tests were cut rather than
kept behind compatibility facades.

## Verification

- `rg` active-contact search found no remaining matches under
  `aria_nbv/aria_nbv` or `aria_nbv/tests`.
- `rg` dependency search found no remaining Captum, Gymnasium,
  stable-baselines3, `cloudpickle`, or Farama dependency references in
  `aria_nbv/pyproject.toml` or `aria_nbv/uv.lock`.
- `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff format` and
  `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff check` passed on touched
  active Python files.
- `uv run --extra dev pytest tests/test_panels_dispatcher.py
  tests/test_config_field_constraints.py
  tests/app/panels/test_counterfactual_rollouts_panel.py` passed with 65 tests.
- `git diff --check` passed.
- `graphify update .` rebuilt the local code graph.

The broader app subset
`uv run --extra dev pytest tests/test_app*.py tests/app` still has the
pre-existing fresh-worktree data-cache failure in
`tests/test_app_state_signature.py::test_config_signature_handles_dataset_and_renderer_configs`
because `.data/ase_efm` has no direct tar shards in this worktree; the other
62 tests in that subset passed.

## Canonical State Impact

No canonical state update is needed. This debrief records the archive execution
and validation evidence only.
