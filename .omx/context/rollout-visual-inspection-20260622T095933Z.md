# Rollout Visual Inspection Ralph Context

## Task Statement

Implement the approved visual-patterns handoff for ARIA-NBV rollout inspection and iteratively improve:

- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`

The user wants first-class Streamlit workflows for counterfactual rollout generation and stored rollout Zarr inspection, using existing ARIA-NBV Plotly/builder/Rerun patterns, with no matplotlib and no external plotting scripts.

## Desired Outcome

- Stored rollout inspection exposes selected-depth availability and bounded visual summaries through `aria_nbv.rollouts.inspection`, not page-local Zarr joins.
- Rollout app pages include clearer explanations for non-trivial plots and dataframe fields through `_info_popover` usage.
- Rollout tree/objective/branching/candidate/target-selection diagnostics become easier to navigate and debug.
- Each successful iteration is tested and committed as a self-contained slice.

## Known Facts / Evidence

- Approved handoff: `.omx/plans/handoff-visual-patterns-20260621T172534Z.json`.
- Guardrails from handoff: tests before selected-depth implementation, bounded dense-array reads, additive UI wiring, rollout tests plus Streamlit panel smoke tests.
- Existing stored rollout page already has store discovery, manual path fallback, validation gating, inventory, objective/branching/target/candidate/geometry/suspicious/metadata tabs, and Rerun launch controls.
- `aria_nbv.rollouts.inspection` owns reusable store summaries and dataframe joins.
- Rerun selected-depth logging already exists in `aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py`.
- Prior memory says zero projected-area targets can be legitimate under current actor-visible target-selection defaults, so visualization should expose projected area and validity context rather than treating zero area as automatically invalid.

## Constraints

- Do not use matplotlib.
- Do not add standalone external plotting scripts.
- Use existing `aria_nbv` plotting utilities and Plotly/builder patterns where possible.
- Preserve unrelated dirty worktree changes.
- Keep selected-depth reads bounded by rollout/step/preview limits.
- Use `PathConfig` and existing app routing/path patterns where paths are touched.
- Follow `aria_nbv/AGENTS.md` and `aria_nbv/aria_nbv/rollouts/AGENTS.md`.

## Unknowns / Open Questions

- Exact selected-depth array names and fixture coverage in current tests.
- Which existing Plotly helpers are cleanly reusable for stored rollout quicklook versus candidate-generation-only diagnostics.
- Whether current Streamlit panel tests can assert UI structure directly or should be smoke-only.

## Likely Codebase Touchpoints

- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/rollouts/__init__.py`
- `aria_nbv/tests/rollouts/test_inspection.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- Existing plotting helpers under `aria_nbv/aria_nbv/pose_generation/plotting.py` and related app utilities.
