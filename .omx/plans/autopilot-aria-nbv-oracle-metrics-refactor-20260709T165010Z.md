# Autopilot RALPLAN: ARIA-NBV Oracle, Metrics, Rollouts Refactor

Created: 2026-07-09T16:50:10Z
Status: blocked-pending-new-consensus-ralplan

> Do not execute this draft. The approved pre-RALPLAN review at
> .omx/specs/autoresearch-aria-nbv-module-pruning-revision-20260710/report.md
> returned REQUEST CHANGES. It identifies unresolved composition cycles,
> scorer/replay DTO ownership, test-only metric machinery, compatibility
> policy, and hard validation gates that this draft does not settle.

## Source Contract

Primary execution source:

- `.omx/specs/autoresearch-aria-nbv-module-pruning-20260709/report.md`

Superseded/corrected sources:

- `.omx/plans/ralplan-rri-rollouts-oracle-pipelines-architecture-20260709T115007Z.md` is superseded.
- `.omx/plans/plan-aria-nbv-oracle-module-refactor-20260709T123231Z.md` is corrected where it suggested formula ownership under `oracle/rewards.py`.

## Clarified Requirements

Implement the report’s immediate workpackages:

1. Lock current behavior and public intent with focused tests/import scans.
2. Deduplicate metric formulas into a metrics-owned gain/return seam.
3. Introduce top-level `aria_nbv.oracle` for evidence, scene RRI, target RRI, labels, crop policy, and oracle pipelines.
4. Move generation ownership from `rollouts` and top-level `pipelines` into `oracle.pipelines`.
5. Narrow `rollouts` toward replay/storage/inspection by removing scorer/generation exports.
6. Apply small safe pruning where it is behavior-preserving.
7. Update guidance/docs/tests for changed ownership.

Report-labeled follow-ups are not mandatory gates for this first implementation unless imports/tests force them:

- Full `data_handling.targets` split.
- Residual `aria_nbv.data` move into `data_handling.downloads`.
- `zarr_store.py` schema engine refactor.
- `rl/` and `interpretability/` archival.

## Proposed Implementation Order

### WP0: Baseline And Contracts

- Inspect current imports and public tests for `rri_metrics.oracle`, `rollouts.target_counterfactuals`, `rollouts.dataset_writer`, and top-level `pipelines`.
- Add/update tests only where contract coverage is missing.
- Record LOC baseline over affected packages.

### WP1: Metrics Formula Owner

- Add a metrics-owned module for gain formulas in current package namespace.
- Move or wrap root-normalized gain, log-error gain, endpoint target gain, endpoint log gain, and discounted selected return through that owner.
- Split core multi-step returns from candidate diagnostics only if it reduces immediate ambiguity without breaking broad call sites.
- Keep behavior identical; tests must compare old/new formula results where feasible.

### WP2: `aria_nbv.oracle` Scoring Boundary

- Create `aria_nbv/aria_nbv/oracle/`.
- Move evidence/scorer semantics from `rri_metrics.oracle` and target/scoring semantics from `rollouts` into oracle modules.
- Avoid broad compatibility facades. Add only test-proven shims and keep them narrow.
- Ensure `oracle` imports metrics formulas; metrics never imports `oracle`.

### WP3: Oracle Pipelines

- Move `pipelines/oracle_rri_labeler.py` into `oracle.pipelines.scene_labeler`.
- Move rollout writer/shard/CLI ownership under `oracle.pipelines` if current tests/imports make it feasible in this pass.
- Update console scripts to stable command names pointing at new modules.

### WP4: Rollouts Narrowing And Safe Pruning

- Remove scorer/generation root exports from `rollouts.__init__` once imports are migrated.
- Keep replay/store/inspection public exports.
- Delete or collapse duplicate helpers such as duplicate `_read_string_array` when tests cover the surface.
- Update `rollouts/AGENTS.md` to reflect replay/storage/inspection ownership.

### WP5: Verification, Review, QA

- Format/lint touched Python files.
- Run targeted pytest for `rri_metrics`, `rollouts`, `data_handling` public contracts, and changed app panel surfaces.
- Run stale import scans.
- Generate limited rollout dataset if local data/configs make it feasible; otherwise record an explicit environment blocker.
- Run code-review and QA gates before completion.

## Acceptance Criteria

- Metric formulas have one owner and no competing implementation in oracle/rollouts.
- `aria_nbv.oracle` exists and owns oracle evidence/scoring/pipelines.
- `rollouts` no longer publicly owns oracle scorers or generation pipelines except for test-proven temporary shims.
- Top-level `pipelines` is either deleted or a narrow temporary shell.
- Guidance files route future work to the corrected owners.
- Net LOC across affected packages is reduced or the remaining increase is justified by removed public DOF and migration of source-owned dirty changes.
- Targeted tests and stale import scans pass, or blockers are explicit and reproducible.
