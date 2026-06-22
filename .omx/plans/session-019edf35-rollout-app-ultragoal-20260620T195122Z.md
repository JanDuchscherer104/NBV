# Session 019edf35 Rollout App Ultragoal Evidence

status: implemented
source_session: 019edf35-6ede-7ab1-907a-44fb067d5221
autopilot_session: 019ee62a-a758-7641-a9c8-e3aa391a3faf

## Scope

Implemented the current-session rollout QA/UI goals without adding an external plotting script:

- Removed the rejected `aria_nbv/scripts/plot_rollout_validation.py` local script.
- Added `rollout_step_objective_rows` to `aria_nbv.rollouts.inspection`.
- Wired a first-class Stored Rollout Zarr Streamlit page.
- Extended the stored rollout panel with Plotly/browser-native per-step objective and branching diagnostics.
- Added focused tests for per-step rollout objective rows and panel export.

## Changed Surfaces

- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/rollouts/__init__.py`
- `aria_nbv/aria_nbv/app/app.py`
- `aria_nbv/aria_nbv/app/panels.py`
- `aria_nbv/aria_nbv/app/panels/__init__.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/tests/rollouts/test_inspection.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`

## Behavior

The new per-step inspection helper joins existing schema arrays only:

- `rollouts/*` for chain, horizon, branch factor, beam width, and temperature.
- `steps/*` for selected candidate, candidate fanout, valid fanout, cumulative target/scene RRI, and cumulative root-gain fields.
- `candidates/*` and dictionary arrays via existing inspection helpers for selected target RRI, root gain, scene RRI, selection probability, sampler probability, strategy, position, mixture, and invalid reason.

`marginal_target_rri` is derived as the step-to-step difference of `steps/cumulative_target_rri` within each rollout. `selected_target_rri` remains the selected candidate's one-step target label.

The Streamlit panel now shows:

- A per-step objective/provenance table.
- Cumulative target RRI by step.
- Marginal target RRI by step.
- Selected-action probability and entropy.
- Candidate fanout and invalid fraction.
- Selected sampling families by policy.

No Matplotlib usage was introduced.

## Verification

Commands passed:

```text
cd aria_nbv && uv run ruff check aria_nbv/app/app.py aria_nbv/app/panels.py aria_nbv/app/panels/__init__.py aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py aria_nbv/rollouts/__init__.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py
All checks passed!
```

```text
cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py -q
3 passed, 15 warnings in 10.06s
```

```text
cd aria_nbv && uv run pytest tests/app/test_rerun_launch.py tests/app/panels/test_counterfactual_rollouts_panel.py -q
29 passed, 15 warnings in 3.27s
```

```text
cd aria_nbv && uv run pytest tests/rerun_inspector/test_rollout_zarr_logger.py -q
9 passed, 1 warning in 8.39s
```

```text
rg -n "matplotlib|plt\\." aria_nbv/aria_nbv/app aria_nbv/aria_nbv/pose_generation aria_nbv/aria_nbv/rerun_inspector
test ! -e aria_nbv/scripts/plot_rollout_validation.py
```

The Matplotlib guard produced no matches and the rejected script path does not exist.

```text
git diff --check -- aria_nbv/aria_nbv/app/app.py aria_nbv/aria_nbv/app/panels.py aria_nbv/aria_nbv/app/panels/__init__.py aria_nbv/aria_nbv/app/panels/stored_rollouts.py aria_nbv/aria_nbv/rollouts/inspection.py aria_nbv/aria_nbv/rollouts/__init__.py aria_nbv/tests/rollouts/test_inspection.py aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
```

No whitespace errors.

## Residual Risk

- The stored rollout page is validated by import/export and helper tests, not by a full live browser Streamlit session yet.
- Visual projection of GT/predicted OBBs into rendered images remains a follow-up in the Rerun/pose-generation visualization lane; this slice adds dataset/UI objective and branching inspection.
