# PRD: Rollout Visual Pattern Inspection

## RALPLAN-DR

Implement a narrow inspection upgrade for the existing Stored rollout Zarr page. The delta is selected-depth and pattern-recognition clarity, not a page rebuild. Keep reusable persisted-store facts in `aria_nbv.rollouts.inspection`, render with Streamlit plus Plotly, and keep dense 3D verification in existing Rerun launch surfaces. Do not add matplotlib, standalone plotting scripts, new dependencies, or schema-changing writes.

## Current Baseline

`aria_nbv/aria_nbv/app/panels/stored_rollouts.py` already provides PathConfig-backed store discovery, selectbox/manual path selection, validation gating, store inventory, objective charts, branching views, candidate/target summaries, geometry plots, suspicious-row triage, metadata views, and rollout-row Rerun launch controls.

`aria_nbv.rollouts.inspection` already owns reusable Zarr joins for inventory, candidate audit rows, target audit rows, validity waterfall rows, candidate group summaries, objective rows, and suspicious-row rows.

## Problem

The remaining weak point is not basic navigation; it is qualitative pattern verification for persisted samples. Operators still need a clear shared contract for selected-depth arrays and a tighter view of how objectives, branch rules, invalidity, and target geometry cohere for a selected sample. Without a data-layer helper, selected-depth quicklooks will drift into page-local Zarr reads.

## Product Goals

- Add an explicit `aria_nbv.rollouts.inspection` selected-depth helper that summarizes enabled/disabled state, row/step alignment, shape, dtype, finite/zero coverage, min/max/quantiles, and selected pose indices for a chosen rollout or bounded set of rollouts.
- Add focused tests for selected-depth inspection, including current schema with selected-depth arrays, disabled/missing selected-depth metadata, and stale/invalid store behavior.
- Add a compact selected-depth quicklook to the existing Stored rollout Zarr page using Plotly heatmap/image-style figures built from inspection rows or bounded arrays returned by an inspection helper.
- Improve existing objective/branch/candidate/target sections only where they lack operator guidance: clearer labels, `_info_popovers`, row filters, and sample-centric defaults.
- Use a rollout-owned plotting/helper surface for persisted-store visuals. Existing pose-generation `CandidatePlotBuilder` may be referenced for conventions, but it is not the primary contract for stored rollout inspection.
- Preserve existing PathConfig discovery, validation, tabs, inventory, and rollout-row Rerun launch behavior unless a targeted simplification is needed.

## Non-goals

- No broad Streamlit page rewrite.
- No new step/candidate-specific Rerun launch contract unless existing `rerun_launch.py` builders already support it.
- No external plotting script generation.
- No matplotlib usage.
- No rollout Zarr schema migration in this slice.
- No production generation policy change.
- No Q_H training or threshold decisions.

## Proposed Design

1. Data layer first
   - Add a pure helper in `aria_nbv.rollouts.inspection`, tentatively `selected_depth_summary_rows(...)`, for metadata/statistical rows.
   - If thumbnails need bounded array payloads, add a separate clearly bounded helper, tentatively `selected_depth_preview_arrays(...)`, with explicit max rows/steps and no mutation.
   - Return serializable row dictionaries for tables and a small bounded array object only for the UI preview path.
   - Stale stores should produce explicit error rows or raise the same validation errors already used by current inspection helpers.

2. Plot helper boundary
   - Add small rollout-owned Plotly figure helpers only when repeated page code would otherwise appear. Candidate/frustum helpers under pose generation can inform style but should not own persisted Zarr store semantics.
   - Keep figure construction Plotly-only and compatible with Streamlit `st.plotly_chart`.

3. UI delta
   - Add a Selected Depth or Depth Quicklook section/tab to the existing page.
   - Default sample filters should bias toward valid or suspicious rows that need qualitative inspection.
   - Add `_info_popovers` for selected depth coverage, objective traces, branch rule labels, invalidity masks, target status, and Rerun launch meaning.
   - Keep stale schema UX explicit: no fake zero-sample success for incompatible stores.

4. Rerun integration
   - Keep current rollout-row and offline-sample launch builders intact.
   - The page may surface copied launch commands/buttons for selected rows, but dense geometry verification remains in existing Rerun inspector code.

## Acceptance Criteria

- Existing store discovery, validation, inventory, objective, branching, target, candidate, geometry, suspicious, metadata, and Rerun launch behavior remains intact.
- Selected-depth metadata/stat rows are produced through `aria_nbv.rollouts.inspection`, not page-local ad hoc Zarr joins.
- The page renders selected-depth quicklook for a current schema store and gives an explicit message for stale/incompatible stores.
- Objective/branch/candidate/target views become easier to interpret through labels, filters, and help popovers without duplicating canonical data logic.
- No matplotlib imports and no standalone validation scripts are introduced.

## Available Agents / Staffing

- `explore`: confirm exact selected-depth arrays/attrs and existing Streamlit helper boundaries.
- `executor`: implement the inspection helper, Plotly helper if needed, and narrow UI delta.
- `test-engineer`: add selected-depth inspection tests and rerun-launch/UI smoke tests where stable.
- `critic` or `code-reviewer`: check boundary leakage, duplicated page logic, and accidental schema/Rerun scope creep.

## Execution Order

1. Add tests that pin selected-depth metadata expectations using existing synthetic Zarr fixtures.
2. Implement `aria_nbv.rollouts.inspection` selected-depth helper(s).
3. Add a small rollout-owned Plotly helper only if the UI would otherwise duplicate plotting code.
4. Wire the selected-depth quicklook and help popovers into `stored_rollouts.py` with minimal page churn.
5. Run targeted tests, ruff, and `git diff --check`.
