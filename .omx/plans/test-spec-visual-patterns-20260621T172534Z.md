# Test Spec: Rollout Visual Pattern Inspection

## Test Scope

Prove the new selected-depth contract and keep existing stored-rollout inspection behavior intact. The implementation should test reusable `aria_nbv.rollouts.inspection` semantics before Streamlit polish.

## Unit Tests

Extend `aria_nbv/tests/rollouts/test_inspection.py` with focused coverage for the new selected-depth helper(s):

- Current schema store with selected-depth arrays returns one row per selected rollout/step or a clearly documented aggregate shape.
- Rows include enabled state, shape, dtype, finite coverage, zero/invalid coverage, min/max/quantile summaries, rollout index, step index, and selected pose/candidate index when stored.
- Disabled or absent selected-depth metadata returns an explicit unavailable status rather than crashing or fabricating zeros.
- Stale/incompatible stores preserve existing validation failure behavior.
- Bounds such as max rows/steps are honored for preview-array helpers.

Keep existing tests for candidate audit rows, target audit rows, objective rows, suspicious rows, and store validation green.

## UI Smoke

If stable Streamlit panel tests exist, add one smoke check that the selected-depth section renders unavailable/current states from mocked inspection rows. If not, keep this as manual verification and rely on data-layer tests.

## Regression Commands

```bash
cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py tests/rollouts/test_info_cli.py tests/rollouts/test_zarr_store.py -q
cd aria_nbv && uv run pytest tests/app/test_rerun_launch.py -q
cd aria_nbv && uv run ruff check aria_nbv/aria_nbv/rollouts/inspection.py aria_nbv/aria_nbv/app/panels/stored_rollouts.py
cd aria_nbv && uv run ruff format --check aria_nbv/aria_nbv/rollouts/inspection.py aria_nbv/aria_nbv/app/panels/stored_rollouts.py
git diff --check
```

## Manual Verification

- Open the Stored rollout Zarr page.
- Select a stale schema store and confirm the error remains explicit.
- Select a current schema store and inspect existing overview/objectives/branching/candidates/targets views for unchanged behavior.
- Inspect the selected-depth quicklook for at least one valid sample and one suspicious sample.
- Launch the same rollout row in Rerun through existing controls and verify depth/pose/target geometry coherence.

## Failure Conditions

- Any matplotlib import or standalone plotting script.
- Any page-local selected-depth Zarr join that should live in `aria_nbv.rollouts.inspection`.
- Any mutation of rollout stores during inspection.
- Any hidden fallback that treats invalid targets as low-RRI labels instead of hard mask/reason state.
- Any broad page rewrite that obscures the existing validated functionality.
