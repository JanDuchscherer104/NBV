# Sandbox

This was a read-only research pass over the source tree plus existing plan
artifacts. No package code was edited.

Primary inspected planning artifacts:

- `.omx/plans/aria-nbv-package-boundary-cleanup-handoff-20260702T162044Z.json`
- `.omx/plans/aria-nbv-package-boundary-cleanup-20260702T162044Z.md`
- `.omx/plans/aria-nbv-package-boundary-cleanup-architect-review-20260702T162044Z.md`
- `.omx/plans/aria-nbv-package-boundary-cleanup-critic-review-20260702T162044Z.md`
- `.omc/plans/plan-aria-nbv-refactor-20260702.md`
- `.agents/memory/history/2026/07/2026-07-02_aria_nbv_slop_audit.md`
- `.omx/context/aria-nbv-package-boundaries-20260702T162044Z.md`
- `.omx/goals/autoresearch/aria-nbv-counterfactual-rollout-generation-thesi/report.md`
- `.agents/refactors.toml`, `.agents/issues.toml`, `.agents/todos.toml`

Primary inspected code surfaces:

- `aria_nbv/aria_nbv/pipelines/oracle_rri_labeler.py`
- `aria_nbv/aria_nbv/rri_metrics/oracle_rri.py`
- `aria_nbv/aria_nbv/pose_generation/counterfactuals.py`
- `aria_nbv/aria_nbv/pose_generation/target_counterfactuals.py`
- `/home/jd/repos/ARIA-NBV-packages/pre-pr15-rollout-boundary/aria_nbv/aria_nbv/rollouts/counterfactuals.py`
- `/home/jd/repos/ARIA-NBV-packages/pre-pr15-rollout-boundary/aria_nbv/aria_nbv/rollouts/target_counterfactuals.py`
- `aria_nbv/aria_nbv/data_handling/__init__.py`
- `aria_nbv/aria_nbv/data_handling/_target_selection.py`
- `aria_nbv/aria_nbv/app/config.py`
- `aria_nbv/aria_nbv/app/panels/rl.py`
- `aria_nbv/aria_nbv/rl/counterfactual_env.py`
- `aria_nbv/tests/data_handling/test_public_api_contract.py`
- `aria_nbv/tests/rl/test_counterfactual_env.py`
- `aria_nbv/tests/app/panels/test_rl_panel.py`
- `aria_nbv/tests/test_config_field_constraints.py`

Notable command evidence:

- Recent artifact inventory found July 2 package-boundary plans as the freshest
  architecture artifacts before the current July 8 autoresearch state.
- Current main checkout is `codex/full-rri-rollout-worktree` and dirty with
  unrelated changes.
- PR15 cleanup worktree `/home/jd/repos/ARIA-NBV-packages/pre-pr15-rollout-boundary`
  is on `codex/pre-pr15-rollout-boundary` at commit `f6d5bf9`, which moved
  counterfactual rollout contracts out of `pose_generation`.
