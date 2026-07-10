# PR15 Review Finding Validity Context

Task: Validate findings in `.agents/work/vin-refactor/PR15_THOROUGH_CODE_REVIEW_HANDOFF_latest-visible-e2ac5a7.md` and recommend which should be implemented.

Desired outcome: Evidence-backed implementation recommendation for PR #15 without source edits in the ralplan session.

Reviewed surface:
- GitHub PR #15: `JanDuchscherer104/ARIA-NBV`, draft, base `main`, head `codex/rollout-diverse-metrics-models`.
- Live GitHub PR head as of this pass: `e2ac5a7e5a32e82bccc15e96f8b8452b7e029f31`.
- Local checkout is not the PR15 tree: current `HEAD` is `5779959` on `codex/full-rri-rollout-worktree`; `git merge-base --is-ancestor e2ac5a7 HEAD` returned false.
- Current checkout has unrelated dirty thesis/scaffold changes; source validation used `git show` / `git grep` against `e2ac5a7`.

Guidance used:
- Root `AGENTS.md`, `aria_nbv/AGENTS.md`, `aria_nbv/aria_nbv/vin/AGENTS.md`, `aria_nbv/aria_nbv/rri_metrics/AGENTS.md`, `aria_nbv/aria_nbv/rollouts/AGENTS.md`.
- `.agents/skills/agent-behavior/SKILL.md`.
- `.agents/skills/code-review-aria-nbv/SKILL.md`.
- `.agents/skills/simplification/SKILL.md`.
- `.agents/references/source_order.md`.
- `.agents/references/verification_matrix.md`.

Evidence highlights:
- `gh pr view 15 --repo JanDuchscherer104/ARIA-NBV --json ...` reports PR head `e2ac5a7...`, draft `true`, `mergeStateStatus=UNSTABLE`, and Root Verification `ci` failure.
- `gh run view 28103149767 --log-failed` shows `make ci` failed at `check-agent-memory` because two history entries reference missing canonical paths.
- `Makefile` at `e2ac5a7` has `ci: agents-db-validate qmd-frontmatter-check check-agent-memory package-smoke docs-render-core`; `package-smoke` runs a fixed small test list and not the new VIN namespace/checkpoint/diagnostic/rollout metric suites.
- `render_vin_diagnostics_page()` at `e2ac5a7` calls `cfg.setup_target(...)`, stores the constructed module, calls `state.module.prepare_for_inference()`, and continues after preparation exceptions with a Streamlit warning.
- `AriaNBVExperimentConfig._init_module_for_resume()` at `e2ac5a7` logs checkpoint resume intent but returns `self.module_config.setup_target()`; actual checkpoint loading is left to trainer execution.
- `VinLightningModule.load_for_inference()` at `e2ac5a7` calls `prepare_for_inference()` before strict `load_state_dict`.
- `prepare_for_inference()` at `e2ac5a7` chooses `config.binner_path` with `elif fallback_binner_path`, so a stale configured path prevents fallback.
- `_maybe_init_coral_bias()` at `e2ac5a7` calls `init_bias_from_priors(..., overwrite=True)`.
- `_step()` at `e2ac5a7` logs all table-level oracle metrics with one `table_log_batch_size = max(int(selected_oracle.valid_table.sum().item()), 1)`.
- `VinModelV3` at `e2ac5a7` lazily registers `self.backbone` in forward and calls `self.to(device)` when the backbone output device differs.
- `TargetConditionedMyopicScorer` and `MultiStepCandidateScorer` are public/exported at `e2ac5a7`; the former is behavior-free for `target_descriptor_dim=0` and rejects positive target descriptors, the latter always raises in `__init__`.
- `CandidateScorer` exposes `head_coral: Any`, `parameters()`, `summarize_vin()`, imports concrete future configs, and defines a concrete config union.
- `vin.__init__` exports many implementation symbols despite describing `VinModelV3` as the active public surface; `vin.types.__init__` exports model-internal DTOs.
- `vin.geometry.voxel.build_scene_field()` defines `unknown = 1 - observed`, while `vin.scorer_context.build_vin_scorer_scene_field()` defines `unknown = 1 - counts_norm`.
- `vin.diagnostics.summary_stats` filters correlation vectors independently and truncates them.
- Duplicate semidense fields and metric keys remain.
- `rri_metrics.logging` owns Lightning `Metric`, `Loss`, `LogSpec`, and metric state; `rri_metrics.torch_rollout_metrics` owns rollout policy metrics.
- `lit_module.py` at `e2ac5a7` is 1298 lines and owns config, checkpoint/binner lifecycle, objective math, metric logging/state, figures, optimizer/scheduler, and hooks.
- `.configs/build_rollouts_v1_diverse.toml` sets `max_samples = 1` and `source.limit = 1`.
- Live PR body still names old paths `target_conditioned_myopic.py` and `multi_step.py`; the `e2ac5a7` files are `target_myopic.py` and `target_finite_horizon.py`.
- `git diff --shortstat main@10487ba7..e2ac5a7` reports `143 files changed, 11764 insertions(+), 3908 deletions(-)`.

Constraints:
- Planning session only; no implementation edits.
- Preserve user/local dirty work.
- Prefer reviewability and cleanup; do not implement Q_H or target-token conditioning in this cleanup.
- Keep `self.vin` checkpoint ownership and historical `vin.*` state-dict prefixes if implementation proceeds.

Open questions:
- Whether PR15 should remain one PR after cleanup or be rebuilt as a smaller commit stack is an execution/release decision.
- Exact local test baseline should be captured in the PR15 branch/worktree before editing; this checkout is not the PR15 tree.
