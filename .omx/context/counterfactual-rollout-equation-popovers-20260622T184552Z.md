# Ralph Context Snapshot: Counterfactual Rollout Equation Popovers

## Task Statement

Implement the requested `_page_counterfactual_rollouts` improvements: plot info boxes must explain the quantities being plotted with equations, especially `J_e^(H)` and `G_t^(H)`, and the explanations must render as Markdown/KaTeX-compatible math.

## Desired Outcome

- The live counterfactual rollout page gives equation-backed theoretical context for the rollout metric dashboard plots.
- Labels distinguish endpoint target gain, root-normalized rollout return, state-relative diagnostic RRI, log gain, candidate fanout, and empirical candidate bands.
- The implementation reuses existing Streamlit helpers and rollout metric semantics instead of duplicating metric computation.

## Known Facts / Evidence

- `aria_nbv/aria_nbv/app/panels/common.py::_info_popover` already renders `st.markdown`, so popover math content can use Markdown display equations.
- `docs/contents/thesis/questions.qmd#rq1-objective` defines target error, endpoint gain `J_{e,\Delta}^{(H)}`, root-normalized immediate reward, finite-horizon return, state-relative diagnostic RRI, and log gain.
- `docs/contents/theory/rl_planning.qmd#transition-reward-return-contract` owns the finite-candidate rollout/Q_H contract.
- `aria_nbv/aria_nbv/rri_metrics/rollout.py` owns implementation helpers for `G_t^(H)`, `J_e^(H)`, and log gain.
- Current panel code computes branch-level `G_target` from selected trajectory summaries and per-step cumulative prefixes from selected root gains.

## Constraints

- Keep the edit scoped to Streamlit panel explanations and tests.
- Do not use matplotlib.
- Use existing Plotly/Streamlit UI patterns.
- Do not move thesis truth into the app beyond compact equations and source-backed explanations.
- Preserve unrelated dirty worktree changes.

## Unknowns / Open Questions

- Whether Streamlit's test harness exposes rendered KaTeX output is uncertain; verify the text constants and import-level behavior rather than relying on visual DOM math output.
- If future UX work wants richer equation components, the shared popover helper may need a structured body API, but this task should not require it.

## Likely Codebase Touchpoints

- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
- Verification: `ruff format`, `ruff check`, targeted pytest for the panel tests.
