# Rollout Field Semantics and Counterfactual UI Alignment

Created: 2026-06-23T09:23:37Z
Status: research-complete; awaiting architect validation

## Executive Verdict

The next implementation should be a four-part alignment slice:

1. Make `docs/typst/thesis/sections/03-02-data-generation.typ` the public thesis owner for target-task, target-selector, rollout, and Q_H-ready field semantics.
2. Extend `docs/typst/shared/equations/entity.typ` rather than inventing a new equation owner for target-selection equations. It already owns `target_descriptor`, target reward, finite-horizon return, endpoint gain, and log gain.
3. Make `render_counterfactual_rollouts_page()` load live-control defaults from `.configs/build_rollouts_v1_realistic.toml` through `PathConfig.resolve_config_toml_path(...)` and `RolloutDatasetWriterConfig.from_toml(...)`.
4. Fix projection semantics deliberately. The current schema fields are `projected_area_pixels` on selector rows and `target_projected_area_pixels` in rollout lineage; the UI display column `projected_area_px` is only a shortened table label. The current implementation is not an aggregate historic frustum projection. It is a max clipped 2D OBB box area across three stored OBB camera slots; zero values are therefore plausible when the source OBB carries no usable `bb2(camera_id)` projection or all projections clip to zero.

The biggest conceptual correction is that there are two target-source contracts:

- `oracle_target_task_sampler`: canonical real rollout data generation. GT OBB identity is the first-pass gate; projection/support/confidence are descriptor and audit fields.
- `actor_visible_selector`: diagnostic/deployable-input V1 selector used by the live Streamlit page today. It ranks actor-visible detected/predicted OBB rows by confidence, visibility, support, and deficit.

The UI and thesis must stop presenting these as one undifferentiated "target selection" procedure.

## Confirmed Current Behavior

### Canonical real rollout config

`.configs/build_rollouts_v1_realistic.toml` is the canonical real rollout profile. It sets:

- `target_source = "oracle_target_task_sampler"`
- `source.split = "train"`
- `max_samples = 25`
- `max_targets_per_sample = 1`
- `target_selector.source_mode = "v1_actor_visible"`
- `target_selector.require_projected_visibility = false`
- candidate mixture: `forward_local=24`, `target_bearing_local=24`, `lateral_target_bypass=12`
- target scorer: `reward_mode = "root_normalized_gain"`, `backprojection_stride = 2`, `target_crop_margin_m = 0.05`

The `target_selector` block remains relevant for V1 diagnostic/deployable-input profiles, but the canonical real writer uses the oracle target-task sampler by default.

### Live Streamlit page contract

`aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py` currently builds live targets with `ActorVisibleTargetSelector(selector_cfg).select(sample)`. Its widget defaults are hard-coded, not loaded from the canonical TOML:

- target `k` default is `3`
- min target support default is `1`
- horizon default is `3`
- target crop margin default is `0.0`
- backprojection stride default is `1`
- the automatic live five-family target mixture preserves the selected candidate budget, default `60`, while manual advanced overrides can diverge from the canonical real three-family `60` shell

This explains why the screenshot can show settings that do not match the canonical real config.

### Actor-visible target-selection equations
<!-- NOTE: don't track composite metrics that are not directly justifiable by intuitive equations. -->

`ActorVisibleTargetSelector` computes:
```text
n_eff = n_semi + w_EVL n_EVL
s_sup = clip(n_eff / n_min, 0, 1)
s_def = 1 - clip(n_eff / n_sat, 0, 1)
S_e = p_e s_vis s_sup s_def
```

Eligibility is hard-masked by finite geometry, confidence, optional projection visibility, and minimum effective support. If `require_projected_visibility=false`, zero projected area does not hard-mask the target; it receives `missing_projection_visibility_score`.

Greedy top-k returns the first `k` ranked eligible rows. Temperature softmax samples without replacement from masked logits derived from the same scores.

### Oracle target-task sampler equations

`OracleTargetTaskSampler` builds the rollout data-generation target-task pool from GT OBB rows. The identity gate is based on self/GT 3D IoU and top-1/top-2 ambiguity:

```text
mu_id(hat e, e) = IoU_3D(hat B_hat_e, B_e)
a_id(hat e) = 1 iff mu_1 >= tau_IoU and mu_1 - mu_2 >= tau_gap
```

Projection/support/confidence are descriptors and audit fields for this sampler. They must not be explained as first-pass eligibility gates for canonical real rollout data.

### Projection field
<!-- NOTE: _max_projected_area should only consider the RGB camera! -->
The current `_max_projected_area(...)` implementation:

1. loops over `camera_id in range(3)`;
2. reads `obb.bb2(camera_id)`;
3. clips `(x1, x2, y1, y2)` to configured image bounds;
4. computes clipped rectangle area; and
5. returns the maximum area.

The attached CSV has 14 rows and all UI-display `projected_area_px == 0`, all `projected_fraction == 0`, and all `visibility_score == 0.35`. In schema terms that means the underlying selector-row `projected_area_pixels` values displayed by the table are zero. That is consistent with the current fallback path, not evidence that support or GT matching failed. Selected rows can still be eligible if effective support passes.

## Field Role Classification

Use this classification in thesis tables and UI info popovers:

| Field                                                                  | Role                                                                                                   |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `target_row_id`                                                        | lineage / selector-local or source-local id                                                            |
| `selected_rank`                                                        | selection output, not input                                                                            |
| `class`, `sem_id`, `inst_id`                                           | descriptor / lineage; semantic compatibility for GT audit                                              |
| `confidence`                                                           | actor-visible selector score factor; oracle sampler descriptor only                                    |
| `projected_area_pixels` / UI `projected_area_px`, `projected_fraction` | current actor-visible selector visibility factor when meaningful; oracle sampler descriptor/audit only |
| `visibility_score`                                                     | actor-visible selector score factor; diagnostic for oracle target tasks                                |
| `semidense_support`, `evl_support`, `effective_support`                | actor-visible selector support gate and score factors; oracle sampler descriptor/audit only            |
| `support_score`, `deficit_score`                                       | actor-visible selector score factors                                                                   |
| `selection_score`                                                      | actor-visible selector interest utility `S_e`; not target-RRI and not Q_H reward                       |
| `selection_probability`                                                | selection-policy output probability                                                                    |
| `eligible`, `invalid_reason`                                           | hard actor-visible selector gate status                                                                |
| `gt_label_valid`, `gt_match_status`, `gt_iou`, `gt_match_score`        | GT/evaluation audit and labelability; not actor-visible input                                          |

For canonical real rollout stores, add a visible source badge:

- "Oracle target task": identity-valid GT task sampled for data generation.
- "Actor-visible diagnostic target": detected/predicted OBB selected by actor-visible evidence.

## Proposed Projection Semantics

The user's proposed interpretation is better than the current overloaded field name for rollout debugging:

```text
A_e^{hist,mean} =
  (1 / |V_e|) sum_{(t,c) in V_e}
    area(clip(project(B_e, K_{t,c}, T_{t,c}), image)) / A_img
```

where `V_e` is the set of valid historic RGB camera slots where the projected OBB intersects the image. Persist both:

- `historic_projected_fraction_mean`: average clipped image fraction over valid historic RGB cameras;
- `historic_projected_fraction_max`: max clipped image fraction over valid historic RGB cameras;
- `historic_projection_observation_count`: number of contributing camera slots.

Do not silently repurpose the existing schema fields without migration. Either rename the current schema field `projected_area_pixels` / persisted rollout lineage field `target_projected_area_pixels` to a source-explicit name in a schema bump, or add new historic-aggregate fields and update UI labels while preserving the old fields. The UI-only `projected_area_px` display label can be changed immediately because it is not the stored schema name. For GT/evaluation clarity, compute actor-visible source OBB projection and matched GT OBB projection separately where both exist.

## Thesis and Shared Equation Ownership

Recommended owners:

- `docs/typst/thesis/sections/03-02-data-generation.typ`: narrative section for target-task sampling, actor-visible diagnostic selector, field-role table, rollout field glossary, and candidate/rollout formulas.
- `docs/typst/shared/equations/entity.typ`: add reusable Typst equations for effective support, projected area, visibility smoothstep, actor-visible eligibility, actor-visible score, greedy top-k, softmax-without-replacement, and oracle identity gate.
- `docs/typst/shared/symbols/entity.typ`: add missing symbols for `S_e`, `s_e^{vis}`, `s_e^{sup}`, `s_e^{def}`, `n_e^{eff}`, `A_e^{proj}`, and identity gate symbols if not already present.
- `docs/contents/theory/candidate_sampling_target_selection.qmd`: keep as a secondary prose/theory page only if it is aligned to the Typst owner. It should not be the sole source for thesis equations.

## Streamlit Implementation Plan

### Slice 1: Load canonical TOML defaults

- Add a small helper used by `render_counterfactual_rollouts_page()` in `counterfactual_rollouts.py`, for example `_load_live_rollout_defaults(config_path: Path | str | None)`.
- Resolve the config path with `PathConfig().resolve_config_toml_path("build_rollouts_v1_realistic.toml")`.
- Parse with `RolloutDatasetWriterConfig.from_toml(...)`.
- Use config-derived defaults for VIN store path, split, target selector, candidate budget, horizon/branch/beam for a selected recipe, target scorer, selected depth, and candidate mixture counts.
- Keep widget overrides interactive, but make the displayed defaults match the TOML.

### Slice 2: Make source mode explicit

- Add a source/protocol selector or badge showing whether the current page is using `ActorVisibleTargetSelector` or the canonical `OracleTargetTaskSampler`.
- If the page only supports live actor-visible selection initially, say that directly in the info popover and link the real rollout writer contract.
- For stored rollout inspection, show `target_source` from the store so users know whether rows came from oracle task sampling or actor-visible selection.

### Slice 3: Equation-aware popovers

Add KaTeX-ready equations to `_SOURCE_TARGET_INFO`, `_LOADED_SAMPLE_INFO`, `_ACTIVE_TARGET_INFO`, `_ROLLOUT_GENERATION_INFO`, and `_SCORER_CONTROLS_INFO`.

The target table popover should include the field-role classification above plus:

```text
n_eff = n_semi + w_EVL n_EVL
s_sup = clip(n_eff / n_min, 0, 1)
s_def = 1 - clip(n_eff / n_sat, 0, 1)
x_e = clip((A_e / A_img) / a_max, 0, 1)
s_vis = x_e^2(3 - 2 x_e)
S_e = p_e s_vis s_sup s_def
E_K = TopK_{e:m_e=1} S_e
```

Also include the oracle identity gate separately so real rollout semantics are clear:

```text
a_id(hat e) = 1 iff mu_1 >= tau_IoU and mu_1 - mu_2 >= tau_gap
```

### Slice 4: Projection fix or rename

Short-term UI fix:

- Rename the UI display label `projected_area_px` to "source bb2 projected area px" or add a warning when all displayed values are zero and fallback visibility is active.
- Explain that current zeros mean no usable source `bb2` support, not necessarily no 3D support.

Implementation fix:

- Add a tested projection aggregator that projects 3D OBB corners into historic RGB cameras using existing geometry/projection utilities.
- Persist new aggregate fields rather than overwriting the old field without a schema bump.
- Add tests for in-frame, out-of-frame, missing camera, and all-zero fallback cases.

## Acceptance Checks for Subsequent Implementation

- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py tests/data_handling/test_target_selection.py -q`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/counterfactual_rollouts.py aria_nbv/data_handling/_target_selection.py`
- `cd docs && typst compile typst/thesis/main.typ --root .` for thesis/equation edits
- `git diff --check`

If projection storage schema changes, also run rollout Zarr tests and writer tests.
