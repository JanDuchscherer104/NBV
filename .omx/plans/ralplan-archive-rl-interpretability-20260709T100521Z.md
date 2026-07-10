# Ralplan: Archive `aria_nbv.rl` and `aria_nbv.interpretability`

## RALPLAN-DR Summary

Principles:
- Hard archive means no active imports, config fields, app pages, tests, or public package exports should depend on the archived modules.
- Preserve unrelated dirty work. Inventory touched paths before edits and do not revert user-owned drift.
- Prefer deletion over compatibility shims; the user stated these modules are not essential and not needed now.
- Keep the archive provenance local under `.agents/archive/aria_nbv/aria_nbv/...`.
- Verify from import/contact evidence, not only from successful file moves.

Decision drivers:
- The modules currently widen the active package scope through Streamlit and tests.
- Streamlit import-time dependencies will break if the directories are moved without removing page/config imports first.
- Dependency metadata can be simplified only after active source and tests stop importing Captum/Gymnasium/SB3.

Viable options:
- Option A: hard archive plus active-surface removal. Move module directories to `.agents/archive/...`, remove Streamlit RL/attribution pages and config fields, delete/retarget module-specific tests, and optionally drop now-unused dependencies. This best matches the request and prior ARIA deprecation practice.
- Option B: archive source but leave compatibility shims in `aria_nbv.rl` and `aria_nbv.interpretability`. This preserves imports but contradicts the stated goal to shrink active package scope and keeps stale public surfaces alive.
- Option C: hide Streamlit pages but leave package modules and tests in place. This is lower risk but does not archive the requested modules and leaves the package scope plowed.

Chosen option:
- Option A, executed in a narrow sequence with a preflight dirty-state inventory and focused validation.

Invalidated alternatives:
- Option B is rejected because compatibility facades keep the modules active.
- Option C is rejected because it does not satisfy the archive requirement.

## Contact Point Inventory

Source modules to archive:
- `aria_nbv/aria_nbv/rl/__init__.py`
- `aria_nbv/aria_nbv/rl/counterfactual_env.py`
- `aria_nbv/aria_nbv/interpretability/__init__.py`
- `aria_nbv/aria_nbv/interpretability/attribution.py`

Streamlit app contact points:
- `aria_nbv/aria_nbv/app/config.py`: imports `CounterfactualPPOConfig` and `CounterfactualRLEnvConfig`; defines `RlPageConfig`; `NbvStreamlitAppConfig` has `rl`.
- `aria_nbv/aria_nbv/app/panels/rl.py`: imports `CounterfactualRLEnv` and `CounterfactualRLEnvConfig`; defines the RL Inspector page helpers and renderer.
- `aria_nbv/aria_nbv/app/panels/testing_attribution.py`: imports `AttributionEngine`, `AttributionMethod`, `BaselineStrategy`, and `InterpretabilityConfig`; defines the Testing & Attribution page.
- `aria_nbv/aria_nbv/app/panels.py`: re-exports `render_rl_page` and `render_testing_attribution_page`.
- `aria_nbv/aria_nbv/app/panels/__init__.py`: re-exports both renderers.
- `aria_nbv/aria_nbv/app/app.py`: imports both renderers, defines `_page_rl` and `_page_testing_attr`, conditionally registers `RL Inspector`, and always registers `Testing & Attribution`.

Test contact points:
- `aria_nbv/tests/rl/test_counterfactual_env.py`: module-specific RL tests, including SB3 smoke.
- `aria_nbv/tests/interpretability/test_attribution.py`: module-specific Captum attribution utility test.
- `aria_nbv/tests/app/panels/test_rl_panel.py`: RL Streamlit helper tests.
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`: imports `RlPageConfig` and asserts the RL page is hidden by default; this must be removed or retargeted when `RlPageConfig` is retired.
- `aria_nbv/tests/test_config_field_constraints.py`: imports `CounterfactualRLEnvConfig` and `RlPageConfig` and checks their validation bounds.
- `aria_nbv/tests/test_panels_dispatcher.py`: imports app panel dispatchers and asserts `render_rl_page`; should be updated when page exports are removed. It currently does not assert Testing & Attribution but importing `aria_nbv.app.panels` still depends on the exported renderer until removed.

Dependency contact points:
- `aria_nbv/pyproject.toml`: direct dependencies `captum`, `gymnasium`, `stable-baselines3`.
- `aria_nbv/uv.lock`: lock entries for those packages.

Docs/backlog contact points:
- `docs/typst/thesis/advisor_meeting_2026_05_22.typ` cites the RL env and panel as advisor-meeting code surfaces.
- `.agents/todos.toml` references `aria_nbv/aria_nbv/rl/counterfactual_env.py`.
- `scripts/quartodoc_expand_config.py` excludes `rl` and `interpretability` from generated API docs. This is not an import edge, but it becomes stale metadata once the modules are archived.

## Implementation Plan

1. Preflight and scope lock:
   - Record `git status --short`.
   - Record focused status for planned touch paths:
     `git status --short -- aria_nbv/aria_nbv/rl aria_nbv/aria_nbv/interpretability aria_nbv/aria_nbv/app/config.py aria_nbv/aria_nbv/app/app.py aria_nbv/aria_nbv/app/panels.py aria_nbv/aria_nbv/app/panels aria_nbv/tests`.
   - If any planned touch path is already dirty, inspect its diff and preserve unrelated changes.

2. Remove Streamlit active edges before moving modules:
   - In `aria_nbv/aria_nbv/app/config.py`, remove `RlPageConfig`, its RL imports, and `NbvStreamlitAppConfig.rl`.
   - In `aria_nbv/aria_nbv/app/app.py`, remove `render_rl_page`, `render_testing_attribution_page`, `_page_rl`, `_page_testing_attr`, and the corresponding `st.Page(...)` registrations.
   - In `aria_nbv/aria_nbv/app/panels.py` and `aria_nbv/aria_nbv/app/panels/__init__.py`, remove exports for the RL and Testing & Attribution renderers.
   - ~Delete active app panel files~ `aria_nbv/aria_nbv/app/panels/rl.py` and `aria_nbv/aria_nbv/app/panels/testing_attribution.py` or **move** them into the archive alongside their owning modules if preserving app-side provenance is desired. The safer default is to archive them under `.agents/archive/aria_nbv/aria_nbv/app/panels/` only if the user wants the app panel source archived too; otherwise delete them as active app glue.

3. Archive module directories:
   - Use `git mv aria_nbv/aria_nbv/interpretability .agents/archive/aria_nbv/aria_nbv/interpretability`.
   - Use `git mv aria_nbv/aria_nbv/rl .agents/archive/aria_nbv/aria_nbv/rl`.
   - Remove any tracked `__pycache__` only if present in git; untracked pycache should not be archived.

4. Remove or retarget tests:
   - Delete module-specific tests:
     `aria_nbv/tests/rl/test_counterfactual_env.py`,
     `aria_nbv/tests/interpretability/test_attribution.py`,
     `aria_nbv/tests/app/panels/test_rl_panel.py`.
   - Update `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py` to remove the `RlPageConfig` import and the hidden-by-default RL page assertion; do not add a replacement unless a remaining counterfactual-rollout contract needs coverage.
   - Update `aria_nbv/tests/test_config_field_constraints.py` to remove `CounterfactualRLEnvConfig` and `RlPageConfig` imports and parametrization.
   - Update `aria_nbv/tests/test_panels_dispatcher.py` to remove `rl` import and `render_rl_page` assertion; add no replacement unless an active page export needs coverage.

5. Dependency cleanup decision:
   - After source/test imports are gone, run `rg -n "captum|gymnasium|stable_baselines3|stable-baselines3|CounterfactualPPOConfig|CounterfactualRLEnvConfig|AttributionEngine|InterpretabilityConfig" aria_nbv/aria_nbv aria_nbv/tests aria_nbv/pyproject.toml`.
   - If only dependency metadata remains, remove `captum`, `gymnasium`, and `stable-baselines3` from `aria_nbv/pyproject.toml` and refresh `aria_nbv/uv.lock` with the repo package workflow.
   - If lock refresh is too broad or blocked by environment issues, leave dependencies for a separate follow-up and document the remaining scope.

6. Docs/backlog handling:
   - Do not rewrite historical advisor-meeting prose by default.
   - If active docs/API generation references the deleted modules, retarget those references to archived paths or remove generated API entries.
   - If touching API-doc generation is in scope, remove stale `rl` and `interpretability` exclusions from `scripts/quartodoc_expand_config.py`; otherwise document that these harmless exclusions remain for a separate cleanup.
   - If `.agents/todos.toml` remains an active actionable item pointing at `aria_nbv/aria_nbv/rl/counterfactual_env.py`, update it through `make agents-db` or mark a follow-up; do not hand-edit backlog TOML ad hoc.

7. Verification:
   - Run focused import/contact search:
     `rg -n "aria_nbv\\.(rl|interpretability)|from \\.\\.\\.(rl|interpretability)|CounterfactualRLEnv|CounterfactualPPOConfig|InterpretabilityConfig|AttributionEngine|RlPageConfig|render_rl_page|render_testing_attribution_page" aria_nbv/aria_nbv aria_nbv/tests`
     Expected: no active source/test hits except archived paths if the search includes `.agents/archive`.
   - Run formatting and lint on touched active Python files.
   - Run focused tests:
     `cd aria_nbv && uv run pytest tests/test_panels_dispatcher.py tests/test_config_field_constraints.py tests/app/panels/test_counterfactual_rollouts_panel.py`
     plus any existing app import/smoke tests matching `tests/test_app*.py` or `tests/app/**` that do not require archived pages.
   - Run `git diff --check`.
   - Run `graphify update .` after edits.

## ADR

Decision:
- Hard-archive `aria_nbv.rl` and `aria_nbv.interpretability` under `.agents/archive/aria_nbv/aria_nbv/` and remove their active Streamlit, test, and export contact points.

Drivers:
- The user explicitly identified both modules as nonessential and not needed at the moment.
- Active Streamlit and test imports keep the modules inside the package's effective public surface.
- Prior ARIA deprecation practice favors source archival plus removal of active construction/export paths over compatibility facades.

Alternatives considered:
- Keep import shims after archival.
- Hide Streamlit pages only.
- Archive only module directories and let failures reveal downstream touchpoints.

Why chosen:
- It is the only option that both archives the requested source and reduces active package scope without leaving stale paths.

Consequences:
- RL Inspector and Testing & Attribution disappear from the Streamlit app.
- RL and interpretability package imports become invalid by design.
- Captum/Gymnasium/SB3 may become removable dependencies if no other active imports remain.
- Historical docs can still mention old paths unless active docs/API checks fail.
- Quartodoc expansion has stale exclusions to remove or explicitly defer.

Follow-ups:
- If RL or interpretability becomes thesis-relevant again, restore from `.agents/archive` deliberately with a fresh owner and tests.
- If dependency cleanup is deferred, open a small follow-up to remove stale package dependencies.

## Available Agent Types

- `explore`: quick repo contact-point verification.
- `executor`: implementation of the archive/removal patch.
- `test-engineer`: focused app/test verification after implementation.
- `verifier`: final import/contact and dirty-diff audit.
- `critic`: review for stale compatibility surfaces or incomplete active-edge removal.

## Follow-Up Staffing Guidance

Recommended default:
- `$ultragoal` for sequential durable execution with checkpoints: preflight inventory, app edge removal, archive move, test/dependency cleanup, verification.

Parallel option:
- `$team` can split into disjoint lanes:
  - Executor A: Streamlit config/dispatcher/page removals.
  - Executor B: archive moves and dependency search/update.
  - Test engineer: update/remove focused tests and run app import tests.
  - Verifier: final `rg`, `git diff --check`, and Graphify update audit.

Ralph fallback:
- `$ralph` is appropriate only if a single-owner persistence loop is explicitly preferred over durable checkpointing.

Suggested reasoning by lane:
- Executor: medium.
- Test engineer: medium.
- Verifier/Critic: high.

Launch hints:
- `omx team` / `$team` is useful only if the dirty worktree is first inventoried and each lane gets disjoint files.
- For native Codex execution outside tmux, prefer direct implementation or `$ultragoal` goal tracking rather than OMX team runtime unless an attached tmux OMX shell is available.

Team verification path:
- Require each lane to report exact touched files.
- Integrator runs the final active-import `rg`, focused pytest, `ruff check`, `git diff --check`, and `graphify update .`.

## Goal-Mode Follow-Up Suggestions

- `$ultragoal`: default for implementing this archive plan with durable checkpoints.
- `$team`: good if parallelizing Streamlit removal, test cleanup, and dependency audit.
- `$ralph`: fallback only for explicit single-owner persistent verification.
