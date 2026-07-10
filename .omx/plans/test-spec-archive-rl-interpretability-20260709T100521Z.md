# Test Spec: Archive RL and Interpretability Modules

## Acceptance Criteria

- `aria_nbv/aria_nbv/rl` no longer exists in the active package and exists at `.agents/archive/aria_nbv/aria_nbv/rl`.
- `aria_nbv/aria_nbv/interpretability` no longer exists in the active package and exists at `.agents/archive/aria_nbv/aria_nbv/interpretability`.
- Active app imports do not require `aria_nbv.rl` or `aria_nbv.interpretability`.
- Streamlit navigation no longer includes `RL Inspector` or `Testing & Attribution`.
- Active tests no longer import archived modules.
- Active tests no longer import or assert `RlPageConfig`.
- Dispatcher/config tests reflect the remaining app surface.
- Optional dependency cleanup removes `captum`, `gymnasium`, and `stable-baselines3` only after active source/test references are gone.
- Optional API-doc generator cleanup removes stale `rl` and `interpretability` exclusions only if that script is touched.

## Required Checks

Preflight:
- `git status --short`
- `git status --short -- aria_nbv/aria_nbv/rl aria_nbv/aria_nbv/interpretability aria_nbv/aria_nbv/app/config.py aria_nbv/aria_nbv/app/app.py aria_nbv/aria_nbv/app/panels.py aria_nbv/aria_nbv/app/panels aria_nbv/tests aria_nbv/pyproject.toml aria_nbv/uv.lock`

Contact search:
```bash
rg -n "aria_nbv\\.(rl|interpretability)|from \\.\\.\\.(rl|interpretability)|CounterfactualRLEnv|CounterfactualPPOConfig|InterpretabilityConfig|AttributionEngine|RlPageConfig|render_rl_page|render_testing_attribution_page|RL Inspector|Testing & Attribution" aria_nbv/aria_nbv aria_nbv/tests
```

Expected after implementation:
- No hits in active `aria_nbv/aria_nbv` or `aria_nbv/tests` except unrelated text that is intentionally retained and explained.

Focused tests:
```bash
cd aria_nbv && uv run pytest tests/test_panels_dispatcher.py tests/test_config_field_constraints.py tests/app/panels/test_counterfactual_rollouts_panel.py
```

Add app smoke/import tests if present:
```bash
cd aria_nbv && uv run pytest tests/test_app*.py tests/app
```

Lint and formatting:
```bash
/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff format <touched-active-python-files>
/home/jd/repos/ARIA-NBV/aria_nbv/.venv/bin/ruff check <touched-active-python-files>
git diff --check
```

Graph refresh:
```bash
graphify update .
```

## Risks

- Existing dirty work overlaps many app/test files; execution must not conflate prior drift with the archive change.
- Removing `RlPageConfig` may require updating any config serialization or tests expecting that field.
- Dependency lock refresh can introduce broad churn; keep it scoped or defer if environment resolution is noisy.
- Historical docs/backlog references may remain by design, but generated API docs must not point to deleted active modules.
- `scripts/quartodoc_expand_config.py` already excludes these roots, so stale entries are low-risk but should be documented if not removed.
