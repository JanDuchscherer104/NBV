# Context Snapshot: Archive RL and Interpretability Modules

Task statement:
- Archive `aria_nbv/aria_nbv/rl` to `.agents/archive/aria_nbv/aria_nbv/rl`.
- Archive `aria_nbv/aria_nbv/interpretability` to `.agents/archive/aria_nbv/aria_nbv/interpretability`.
- Start by identifying all contact points with tests and the Streamlit app.
- Use Graphify and other available tools.

Desired outcome:
- The active `aria_nbv` package no longer exposes or imports the nonessential RL and interpretability modules.
- Streamlit no longer registers pages or app config fields that require those archived modules.
- Tests no longer import archived package paths; either remove module-specific tests or retarget dispatcher/config tests to the remaining active surface.
- The archived source remains under `.agents/archive/...` with history-preserving moves in the execution lane.

Mode and constraints:
- Active workflow is `$ralplan`, planning-only until explicit execution handoff.
- Code moves and source edits are out of scope for this planning step.
- Worktree is already dirty across many app, tests, docs, and package files; execution must inventory exact dirty state before touching overlapping paths and must not revert unrelated changes.
- Prior ARIA archive/deprecation memory supports hard archival plus active-surface removal, not compatibility facades, when the user explicitly asks for source to move under `.agents/archive`.

Evidence gathered:
- `graphify-out/graph.json` exists and was queried.
- Graphify query surfaced `aria_nbv/aria_nbv/app/panels/rl.py`, `aria_nbv/aria_nbv/app/panels/testing_attribution.py`, `aria_nbv/aria_nbv/app/app.py`, `aria_nbv/aria_nbv/app/panels.py`, `aria_nbv/aria_nbv/app/panels/__init__.py`, and `aria_nbv/aria_nbv/app/config.py` among the app-side contact points.
- Graphify path checks:
  - `rl.py --imports--> CounterfactualRLEnv <--contains-- counterfactual_env.py`
  - `testing_attribution.py --imports_from--> attribution.py`
- AST import scan over `aria_nbv/aria_nbv` and `aria_nbv/tests` found these direct imports of `aria_nbv.rl` or `aria_nbv.interpretability`:
  - `aria_nbv/aria_nbv/app/config.py:11`
  - `aria_nbv/aria_nbv/app/panels/rl.py:18`
  - `aria_nbv/aria_nbv/app/panels/testing_attribution.py:15`
  - `aria_nbv/aria_nbv/interpretability/__init__.py:3`
  - `aria_nbv/aria_nbv/rl/__init__.py:3`
  - `aria_nbv/tests/app/panels/test_rl_panel.py:12`
  - `aria_nbv/tests/interpretability/test_attribution.py:6`
  - `aria_nbv/tests/rl/test_counterfactual_env.py:21`
  - `aria_nbv/tests/test_config_field_constraints.py:30`
- A broader app-test search found additional `RlPageConfig` consumers that do not import `aria_nbv.rl` directly but will break when the RL app config is retired:
  - `aria_nbv/tests/test_config_field_constraints.py:12` imports `RlPageConfig`
  - `aria_nbv/tests/test_config_field_constraints.py:90` validates `RlPageConfig(default_eval_episodes=0)`
  - `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:22` imports `RlPageConfig`
  - `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:839` asserts `RlPageConfig().enabled is False`

Likely codebase touchpoints:
- Module sources to archive:
  - `aria_nbv/aria_nbv/rl/__init__.py`
  - `aria_nbv/aria_nbv/rl/counterfactual_env.py`
  - `aria_nbv/aria_nbv/interpretability/__init__.py`
  - `aria_nbv/aria_nbv/interpretability/attribution.py`
- Streamlit app surfaces to remove or simplify:
  - `aria_nbv/aria_nbv/app/config.py`
  - `aria_nbv/aria_nbv/app/app.py`
  - `aria_nbv/aria_nbv/app/panels.py`
  - `aria_nbv/aria_nbv/app/panels/__init__.py`
  - `aria_nbv/aria_nbv/app/panels/rl.py`
  - `aria_nbv/aria_nbv/app/panels/testing_attribution.py`
- Tests to delete or retarget:
  - `aria_nbv/tests/rl/test_counterfactual_env.py`
  - `aria_nbv/tests/interpretability/test_attribution.py`
  - `aria_nbv/tests/app/panels/test_rl_panel.py`
  - `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`
  - `aria_nbv/tests/test_config_field_constraints.py`
  - `aria_nbv/tests/test_panels_dispatcher.py`
- Dependency metadata:
  - `aria_nbv/pyproject.toml` has direct dependencies `captum`, `gymnasium`, and `stable-baselines3` that are only indicated by the archived surfaces in the inspected source.
  - `aria_nbv/uv.lock` contains matching locked packages; execution should update the lock with the repo's package workflow only if dependency removal is included.
- Docs/backlog references:
  - `docs/typst/thesis/advisor_meeting_2026_05_22.typ` references `aria_nbv/aria_nbv/rl/counterfactual_env.py` and `aria_nbv/aria_nbv/app/panels/rl.py` as historical/advisor surfaces.
  - `.agents/todos.toml` references `aria_nbv/aria_nbv/rl/counterfactual_env.py` in a planning item. Execution should decide whether to retarget this through `agents-db` or leave as historical backlog evidence.
  - `scripts/quartodoc_expand_config.py` lists `rl` and `interpretability` in `EXCLUDED_ROOTS`; this is not an active import, but execution should decide whether to remove stale exclusions after the packages are archived.

Unknowns/open questions:
- Whether dependency removal from `pyproject.toml` and `uv.lock` should be part of the same execution slice. It is a natural cleanup if no other active imports remain, but it broadens verification.
- Whether docs/advisor historical references should be rewritten to archived paths in the same change. The narrow archive scope can leave historical docs alone unless active docs/API generation break.
- Whether stale Quartodoc exclusions should be removed now or left harmlessly as historical exclusions.

Baseline verification candidates:
- Import/contact probe: `rg -n "aria_nbv\\.(rl|interpretability)|from \\.\\.\\.(rl|interpretability)|CounterfactualRLEnv|CounterfactualPPOConfig|InterpretabilityConfig|AttributionEngine|RlPageConfig|render_rl_page|render_testing_attribution_page" aria_nbv/aria_nbv aria_nbv/tests`
- Focused tests after removal:
  - `cd aria_nbv && uv run pytest tests/test_panels_dispatcher.py tests/test_config_field_constraints.py tests/app/panels/test_counterfactual_rollouts_panel.py`
  - Include any app smoke/import tests that exist after inspection, e.g. `tests/test_app*.py` or `tests/app/**`.
- Static checks:
  - `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff format <touched-python-files>`
  - `/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff check <touched-python-files>`
  - `git diff --check`
- Graph maintenance:
  - `graphify update .` after code changes.
