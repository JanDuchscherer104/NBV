# Autopilot Context: ARIA-NBV Oracle, Metrics, Rollouts Refactor

Created: 2026-07-09T16:50:10Z

## Activation Prompt

`$oh-my-codex:autopilot implement all suggestions as per autoresearch report.`

## Original Task Status

activation-prompt

## Desired Outcome

Implement the corrected `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md` recommendations through the Autopilot sequence:

1. Clarification gate based on the report.
2. Consensus implementation plan.
3. Durable implementation and verification.
4. Independent code review.
5. QA or explicit skip with evidence.

## Known Facts And Evidence

- The report states the key rule: metric formulas live in metrics; oracle code prepares evidence and emits labels by calling those formulas; rollouts replay and store generated evidence; data handling owns source data, target rows, target selection, and offline caches.
- The older RALPLAN that kept generation in top-level `pipelines` is superseded.
- The later oracle plan is corrected where it implied `oracle/rewards.py` should own gain formulas.
- Graphify query on 2026-07-09 found the same coupled implementation cluster: `rollouts.counterfactuals`, `rollouts.target_counterfactuals`, `rollouts.dataset_writer`, `rollouts.zarr_store`, `rri_metrics.metrics.multi_step`, `rri_metrics.oracle`, `pipelines.oracle_rri_labeler`, and `data_handling._target_selection`.
- The worktree is already dirty on many relevant files; unrelated user/agent changes must be preserved.

## Constraints

- Do not revert unrelated dirty changes.
- Do not add new dependencies.
- Prefer deletion and direct ownership moves over compatibility wrappers.
- Keep formula ownership in metrics, not oracle.
- Keep rollout replay/storage in `rollouts`; do not move rollout Zarr into `data_handling`.
- Keep the first implementation pass focused on report-approved immediate work; report-labeled later/separate items stay out unless needed by imports/tests.
- Validate with targeted lint/tests and stale-import scans.

## Unknowns / Open Questions

- How much of the pre-existing dirty worktree is already a partial rri_metrics hierarchy refactor and must be preserved.
- Whether existing public contract tests require temporary compatibility shells for `pipelines` or old `rri_metrics.oracle` imports.
- Whether full rollout dataset generation is feasible in the current local environment without data/cache credentials.

## Likely Codebase Touchpoints

- `aria_nbv/aria_nbv/rri_metrics/**`
- `aria_nbv/aria_nbv/rollouts/**`
- `aria_nbv/aria_nbv/pipelines/**`
- new `aria_nbv/aria_nbv/oracle/**`
- `aria_nbv/pyproject.toml`
- tests under `aria_nbv/tests/rri_metrics`, `aria_nbv/tests/rollouts`, `aria_nbv/tests/data_handling`, and app panel tests
- docs/reference paths if public API paths change

## Scope Note

This context snapshot is derived from the Autopilot activation prompt plus the current autoresearch report. It is not a complete transcript of prior conversation context.
