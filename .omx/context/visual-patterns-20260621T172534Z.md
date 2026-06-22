# Rollout Visual Patterns Context

## Task Statement

Plan implementation for intuitive rollout sample visualizations that help understand sample patterns, integrated with existing ARIA-NBV plotting helpers, Streamlit pages, and Rerun inspection.

## Desired Outcome

- Existing rollout Zarr stores can be browsed from Streamlit and understood at the store, rollout, step, candidate, target, and selected-depth levels.
- Users can quickly answer which stores are current, which rows look suspicious, which candidate families dominate selected paths, why candidates are invalid, whether selected depths and target geometry look coherent, and which sample should be opened in Rerun.
- Figure construction remains Plotly/builder-pattern based and repo-native.

## Known Facts / Evidence

- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py` owns the Stored Rollout Zarr page with store discovery, validation gating, current tabs, and Rerun launch controls.
- `stored_rollouts.py` already renders Plotly objective, branching, candidate, target, and geometry charts.
- `aria_nbv/aria_nbv/rollouts/inspection.py` is the correct data-join layer and keeps UI/CLI/tests away from ad hoc Zarr joins.
- `rollouts.inspection` already provides candidate, target, validity, objective, and suspicious-row helper rows.
- `aria_nbv/aria_nbv/pose_generation/plotting.py` already contains Plotly and builder-pattern candidate/frustum plotting helpers.
- `aria_nbv/tests/rollouts/test_inspection.py` already tests rollout inspection joins and suspicious-row helpers.
- Repo dependencies include Streamlit, Plotly, and Rerun SDK; no new dependency is needed.

## Constraints

- No matplotlib for rollout validation plots.
- No standalone external plotting scripts.
- Keep Zarr schema/read semantics in `aria_nbv.rollouts`, not Streamlit.
- Keep Streamlit as orchestration/UI and Rerun as dense 3D verifier.
- Preserve current schema validation gates for stale stores.
- Do not mutate rollout stores during inspection.
- Follow `PathConfig` for path handling.
- Preserve unrelated dirty worktree changes.

## Unknowns / Open Questions

- Large production stores need row limits and filters before all-row rendering.
- Selected-depth thumbnails should use Plotly heatmap/image grids in the first pass.
- Rerun candidate/step launch may require a later CLI extension; keep rollout-level launch first if needed.

## Likely Touchpoints

- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/aria_nbv/pose_generation/plotting.py` or a new rollout plotting helper under `aria_nbv/aria_nbv/rollouts/`
- `aria_nbv/tests/rollouts/test_inspection.py`
- Streamlit panel tests under `aria_nbv/tests/app/` if an existing pattern is available.
