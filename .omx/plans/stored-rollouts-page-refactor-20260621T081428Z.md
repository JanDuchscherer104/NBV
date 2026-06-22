# Stored Rollout Zarr Page Refactor Plan

Mode: `$plan` direct mode.
Scope: revise and refactor `_page_stored_rollouts` / `render_stored_rollouts_panel` so it is an inventory-first rollout-store inspection page, uses `PathConfig`, and removes obvious UI/path-handling slop without changing rollout schema generation.

## Requirements Summary

- Make the page useful before the selected store validates against the current schema.
- Discover rollout stores from the configured cache root instead of requiring a pasted path.
- Use `PathConfig` for repo-root, cache, config, and artifact path resolution.
- Show all discovered `*.zarr` rollout stores with current/stale schema, row counts, validity, lineage, and storage information.
- Keep current-schema deep inspection behind validation, but keep stale-store diagnosis visible.
- Add help popovers near the controls that currently cause confusion.
- Keep plotting inside Streamlit with Plotly / existing ARIA-NBV plotting helpers. Do not add standalone scripts or matplotlib.
- Prune obvious slop: hardcoded paths, stale TODO, path text boxes as the primary selector, repeated ad hoc table/chart blocks, and early returns that hide useful diagnosis.

## Evidence From Current Code

- `render_stored_rollouts_panel` still hardcodes the default store, Rerun config, and RRD directory through `repo_root()` and raw `Path(...)` text inputs (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:72-89`).
- The file already admits this is wrong: the TODO asks to use `PathConfig` for all path handling (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:64`).
- `PathConfig` exposes the configured offline cache root (`aria_nbv/aria_nbv/configs/path_config.py:67`), cache artifact resolution (`aria_nbv/aria_nbv/configs/path_config.py:343-363`), and TOML config resolution (`aria_nbv/aria_nbv/configs/path_config.py:397-417`).
- The current UI displays validation counts from `reader.validate()` (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:103-113`), but the validator returns `0, 0, 0` as soon as root-contract errors exist (`aria_nbv/aria_nbv/rollouts/zarr_store.py:663-668`). That is why stale stores can look empty even when groups contain rows.
- The current page returns immediately on invalid schema (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:120-125`), hiding inventory, manifest, stale-schema counts, and remediation context.
- Current expected rollout schema is `1.0-target-rollout-core` (`aria_nbv/aria_nbv/rollouts/zarr_store.py:68`), and current required groups include `candidate_diagnostics` and `target_eval_crops` (`aria_nbv/aria_nbv/rollouts/zarr_store.py:1121-1135`).
- The app already exposes this as a first-class page (`aria_nbv/aria_nbv/app/app.py:161-162`, `aria_nbv/aria_nbv/app/app.py:254-259`), so this refactor should improve the existing page, not create another entrypoint.
- The rollout inspection module is already the right home for read-only Zarr joins used by Streamlit, CLI, and tests (`aria_nbv/aria_nbv/rollouts/inspection.py:1-5`).
- Current objective and branching plots are present but monolithic in the panel (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:262-388`).
- Current QA tabs cover validity, targets, candidate groups, geometry, and suspicious rows (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:391-562`), but the page lacks a store inventory and schema-aware navigation.
- Existing live rollout geometry uses `CounterfactualPlotBuilder` plus shared scene options (`aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py:1196-1214`, `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py:1286-1309`) and shared scene overlays (`aria_nbv/aria_nbv/app/scene_view.py:208-255`). Stored-store geometry should reuse these patterns only when the persisted store has enough source/sample context.
- `_info_popover` is available as the existing help mechanism (`aria_nbv/aria_nbv/app/panels/common.py:19-21`), but the stored page currently only uses it at the top and before candidate rows (`aria_nbv/aria_nbv/app/panels/stored_rollouts.py:70`, `aria_nbv/aria_nbv/app/panels/stored_rollouts.py:144`).
- Current tests cover rollout option formatting and public export (`aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py:220-256`) plus inspection helper joins/objective rows (`aria_nbv/tests/rollouts/test_inspection.py:28-126`).

## Design Principles

1. Inventory before inspection: users should immediately see which stores exist and why a selected one is current, stale, empty, or broken.
2. Schema-aware degradation: stale stores are not deep-inspected, but they are still counted, identified, and explained.
3. Thin Streamlit, testable helpers: Zarr reading, schema summaries, and row-count extraction belong in read-only helpers; Streamlit renders rows and figures.
4. No duplicate truth: the page should point to schema attrs, manifest fields, and rollout arrays instead of restating rollout contracts.
5. No new plotting lane: use Plotly and existing ARIA-NBV builder/helper patterns; no external scripts and no matplotlib.

## Viable Options

### Option A: UI-only refactor in `stored_rollouts.py`

Pros:
- Smallest diff.
- Fast to implement.
- Keeps all page behavior in one file.

Cons:
- Zarr inventory/count logic remains hard to test without Streamlit.
- More likely to accumulate another block of panel-local slop.
- CLI and future preflight pages cannot reuse store discovery.

### Option B: Add read-only inventory helpers in `aria_nbv.rollouts.inspection`

Pros:
- Matches the current module contract: helpers return plain dict rows for UI/CLI/tests.
- Makes stale-store counting and manifest/schema summaries unit-testable.
- Keeps Streamlit as renderer/controller only.

Cons:
- Slightly wider diff because `inspection.py`, exports, and tests change.
- Must avoid putting app-specific labels or Streamlit state in rollout helpers.

Chosen option: Option B. The helper boundary is already established, and this task is mostly about making path/schema/store inspection reliable rather than decorating the page.

## Implementation Steps

### 1. Add store inventory helpers

Files:
- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/rollouts/__init__.py`
- `aria_nbv/tests/rollouts/test_inspection.py`

Add:
- `discover_rollout_store_paths(base_dir: Path, *, pattern: str = "**/*.zarr") -> list[Path]`
- `rollout_store_inventory_rows(store_paths: Iterable[Path]) -> list[dict[str, object]]`
- a small internal helper that safely reads:
  - root attrs: `schema_id`, `schema_version`, `created_at`, `manifest_path`
  - manifest schema/version/profile/source coverage when present
  - observed array counts from `rollouts/rollout_row_id`, `steps/step_row_id`, and `candidates/candidate_row_id`
  - validation status/errors when `RolloutZarrStoreReader(...).validate()` can run
  - required group presence for current-schema diagnostics
  - file count and approximate byte size

Acceptance:
- Valid current-schema stores report `schema_status == "current"` and validation counts.
- Stale stores report actual observed counts when arrays exist, even when current validation returns zero.
- Broken/unopenable stores produce one row with `schema_status == "unreadable"` and an actionable error string.
- Helpers do not import Streamlit.

### 2. Replace raw path entry with `PathConfig`-backed selection

Files:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`

Change:
- Instantiate `PathConfig()` in the panel.
- Use `path_config.offline_cache_dir` as the primary discovery root.
- Use `path_config.resolve_config_toml_path("rerun_offline.toml", must_exist=True)` for the default Rerun config.
- Use `path_config.resolve_run_dir(".artifacts/rerun")` or another existing `PathConfig` helper for the default RRD directory.
- Replace the primary `rollouts.zarr path` text input with an `st.selectbox` over discovered stores.
- Keep a compact advanced/manual override expander for an arbitrary absolute store path, but route it through `PathConfig.resolve_cache_artifact_dir`.
- Remove the line-64 TODO once the refactor lands.

Acceptance:
- The page loads with no typed path when at least one store exists under `offline_cache_dir`.
- Store labels include relative path, schema status, validation status, observed rollout/step/candidate counts, and mtime.
- Manual override is secondary and never bypasses `PathConfig`.

### 3. Add the store inventory section

Files:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py`

Render before selected-store details:
- A "Rollout Stores" table with:
  - relative path
  - schema version and current/stale/unreadable status
  - validation OK/failed/not run
  - observed rollouts, steps, candidates
  - validator counts where available
  - candidate valid fraction / q-train fraction when current-schema arrays exist
  - policy/horizon/branch-factor summary when current-schema arrays exist
  - manifest schema version, profile/config stem, source split/scene count when manifest fields exist
  - store mtime, size, file count
  - first error
- Add help via `_info_popover("store discovery", ...)` and `_info_popover("schema status", ...)`.

Acceptance:
- A stale `0.6-rollout-core` store visibly shows it is stale rather than empty.
- Current-schema stores sort above stale stores; newest stores sort within status groups.
- Errors are compact in the table and full validation errors remain available in an expander.

### 4. Rework selected-store navigation into tabs

Files:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`

Use a single selected store, then render:
- `Overview`: metrics, source coverage, target validity summary, root/manifest snippets.
- `Validation`: validator result, required-group status, validation errors, stale remediation.
- `Objectives`: rollout-level endpoint metrics plus per-step cumulative and marginal RRI.
- `Branching`: chain/step fanout, selected strategy/position/mixture, sampler probability and entropy.
- `Targets`: target audit table and target score/support plots.
- `Candidates`: candidate groups and selected rollout candidate rows.
- `Geometry`: candidate diagnostics histograms/heatmaps; optional Rerun launch link.
- `Suspicious`: suspicious-row query controls and rerun command for selected suspicious rollout.
- `Metadata`: raw root attrs and manifest JSON.

For stale/invalid stores:
- Enable `Overview`, `Validation`, and `Metadata`.
- Disable or replace deep tabs with clear "requires current schema" info blocks.
- Do not call helper functions that assume `candidate_diagnostics` or `target_eval_crops` when those groups are absent.

Acceptance:
- The page no longer returns before showing useful stale-store diagnosis.
- Deep current-schema tabs remain visually reachable but clearly gated.
- The selected rollout candidate table still uses `candidate_rows_for_rollout`.

### 5. Add focused help popovers

File:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`

Add `_info_popover` blocks near:
- store discovery/root selection
- schema and validation
- rollout/step/candidate counts
- objective metrics: cumulative target RRI, marginal target RRI, target root gain, scene RRI
- branching/provenance: policy, chain, branch factor, beam width, selected strategy/position/mixture
- masks: actor action, oracle label, q-train, selected
- target audit: actor-visible target versus GT/eval target validity
- geometry diagnostics: path collision, clearance, motion, target bearing/distance
- Rerun launch: native command, web viewer ports, RRD save directory

Acceptance:
- Help text explains interpretation boundaries, not implementation history.
- Help text does not duplicate schema definitions that are better read from attrs/manifest.

### 6. Prune obvious slop during the refactor

Files:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/aria_nbv/rollouts/inspection.py`

Remove or collapse:
- `repo_root()` path defaults in this panel.
- direct `Path(st.text_input(...)).expanduser()` as the primary path surface.
- the stale TODO once fixed.
- repeated "make dataframe, then bar chart" blocks where a tiny local renderer helper improves clarity.
- chart code embedded in validation/control sections when it can become `_render_*` functions with one purpose.
- `return` paths that suppress metadata/inventory after a recoverable validation failure.

Keep:
- `format_rollout_option` as a small public helper because tests already cover it.
- `candidate_rows_for_rollout` unless it becomes an unnecessary wrapper after tests move to `candidate_audit_rows`.

Acceptance:
- The panel is easier to skim: top-level function reads as select store -> inventory -> selected summary -> schema-gated tabs -> rerun launch.
- No broad abstraction layer or new dependency is introduced.

### 7. Optional geometry bridge, only if persisted context exists

Files:
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- possibly `aria_nbv/aria_nbv/rollouts/inspection.py`

Do not reconstruct live `CounterfactualRollouts` from partial store data in this slice unless the required source sample/context is already available and cheaply loaded.

If enough context exists, add an optional "Open matching live scene view" or stored-step geometry visualization that reuses:
- `CounterfactualPlotBuilder`
- `apply_scene_plot_options`
- current target overlay helpers or a shared helper extracted from live counterfactual rollouts

Acceptance:
- No brittle pseudo-rollout objects.
- If context is missing, the page says which persisted/source fields are missing and routes the user to Rerun instead.

## Test Plan

Unit/helper tests:
- `cd aria_nbv && uv run pytest tests/rollouts/test_inspection.py -q`
- Add tests for discovery sorting, current-schema inventory rows, stale-schema inventory rows, and unreadable/broken stores.
- Add a stale-store fixture by creating a minimal Zarr with `schema_version="0.6-rollout-core"` and basic `rollouts`, `steps`, `candidates` arrays. Assert observed counts are nonzero and validation status is stale/failed.

App-panel tests:
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- Add tests for store-label formatting and `PathConfig`-resolved defaults where practical without invoking Streamlit runtime.

Static checks:
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff format aria_nbv/app/panels/stored_rollouts.py aria_nbv/rollouts/inspection.py tests/rollouts/test_inspection.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `git diff --check`

Smoke check:
- Start Streamlit after implementation:
  - `cd aria_nbv && uv run nbv-st --server.address 0.0.0.0 --server.port 8503 --server.headless true`
- Verify the Stored Rollout Zarr page loads, the inventory table appears, and a stale store shows observed counts plus schema mismatch instead of only zero metrics.

Optional rollout CLI cross-check:
- For a current fresh store, compare the page inventory counts against:
  - `cd aria_nbv && uv run nbv-rollouts-info --store <store> --validate --stats --json`

## Non-Goals

- Do not migrate or rewrite stale `0.6-rollout-core` stores.
- Do not change `ROLLOUT_ZARR_SCHEMA_VERSION`.
- Do not change rollout writer semantics, invalidity masks, target sampling, or `Q_H` reward definitions.
- Do not add a standalone validation plotting script.
- Do not add matplotlib.
- Do not make Streamlit the canonical rollout schema validator.

## Risks And Mitigations

- Risk: inventory helpers accidentally treat stale stores as valid.
  - Mitigation: separate `schema_status`, `validation_ok`, `observed_*_count`, and `validator_*_count` fields.
- Risk: `PathConfig` singleton state makes tests brittle.
  - Mitigation: keep pure discovery helpers independent of `PathConfig`; use `PathConfig` only in the panel/controller layer.
- Risk: UI grows into another large monolith.
  - Mitigation: organize top-level rendering into small `_render_store_inventory`, `_render_selected_store_overview`, `_render_validation_tab`, `_render_objectives_tab`, etc.
- Risk: deep tabs crash on stale stores.
  - Mitigation: gate current-schema-only helpers behind validation/group checks, and add stale-store tests.
- Risk: geometry visualization duplicates the live rollout page.
  - Mitigation: defer geometry builder reuse unless persisted context is sufficient; otherwise route to Rerun.

## Execution Order

1. Implement read-only inventory helpers and tests.
2. Refactor path selection to `PathConfig` and `st.selectbox`.
3. Add inventory table and stale-schema selected-store overview.
4. Move existing current-schema summaries into schema-gated tabs.
5. Add help popovers and prune dead/hardcoded slop.
6. Run targeted tests, ruff, `git diff --check`, and a Streamlit smoke.

## Definition Of Done

- Opening the page with the stale `rollouts_v1_smoke.zarr` no longer implies "zero rollouts"; it shows stale schema plus observed group counts.
- A current-schema store can still be inspected through objectives, branching, targets, candidates, geometry, suspicious rows, and Rerun launch.
- All primary paths come from `PathConfig`.
- The target page contains no matplotlib usage and no external plotting script.
- The refactor has focused tests for helper behavior and existing panel public helpers.
