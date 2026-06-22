"""Streamlit helpers for inspecting persisted rollout Zarr stores."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import torch

from ...configs import PathConfig
from ...rendering.plotting import depth_grid
from ...rollouts import (
    RolloutSuspiciousQueryConfig,
    RolloutZarrStoreReader,
    candidate_audit_rows,
    candidate_group_summary_rows,
    discover_rollout_store_paths,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    rollout_tree_summary_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    suspicious_rollout_rows,
    target_audit_rows,
    validity_waterfall_rows,
)
from ..rerun_launch import (
    build_rerun_rollout_spawn_command,
    build_rerun_rollout_web_command,
    format_command,
    rerun_web_url,
    spawn_background_command,
)
from .common import _info_popover, _report_exception

_STORED_ROLLOUTS_INFO = """
Stored rollouts inspect a standalone `rollouts.zarr` shard without recomputation.

- Validation metadata checks table/mask consistency before inspection.
- The manifest records source/config lineage and source coverage.
- Target summary separates actor target validity from GT-label validity.
- Candidate rows show `actor_action`, `q_train`, target/scene labels, root gains, motion diagnostics, and strategy/position/mixture provenance.
- `q_train` marks rows usable for finite-candidate `Q_H` training views.
- QA tabs expose validity waterfalls, invalidity distributions, rollout geometry, and suspicious rows before opening a dense Rerun inspection.
- Rerun launch opens or serves the selected rollout row in the 3D inspector.
"""

_STORE_DISCOVERY_INFO = """
The selector scans the configured `PathConfig.offline_cache_dir` recursively for `*.zarr` directories.
Use the manual override only for a store outside the normal cache root; relative overrides are resolved as cache artifacts.
"""

_SCHEMA_VALIDATION_INFO = """
Schema status and validation are separate:

- `current` means the root `schema_version` matches the code.
- `stale` means the store may still contain rows, but current deep inspection is gated.
- observed counts read arrays directly and may be nonzero even when validator counts are zero.
- validation errors explain which current-schema contract blocks deep tabs and Rerun launch.
"""

_COUNTS_INFO = """
Observed counts are lightweight direct reads from `rollouts/`, `steps/`, and `candidates/`.
Validator counts come from the current schema validator and intentionally become zero when root-contract checks fail.
"""

_STORE_INVENTORY_INFO = """
The inventory table is the first triage surface for every discovered `*.zarr` store.

- `schema`: `current` can use all deep tabs; `stale` or `unreadable` stays in overview/metadata only.
- `validation`: current-schema contract result from `RolloutZarrStoreReader.validate()`.
- `observed_*`: direct array counts, useful even when schema validation fails.
- `validator_*`: counts returned by the current validator; zero usually means a root/schema gate failed.
- `actor_action_fraction` / `q_train_fraction`: candidate-mask health for deployable actions and finite-candidate training cells.
- `policies`, `horizons`, and `branch_factors`: quick diversity clues for the shard.
- `manifest`, `profile`, and `config`: generation lineage from the rollout manifest sidecar.
- `missing_groups` and `first_error`: the fastest way to decide whether to regenerate, migrate, or inspect manually.
"""

_OBJECTIVE_INFO = """
Objective plots use persisted rollout arrays only. Cumulative target RRI tracks the rollout path total, marginal target RRI is the step-to-step delta, and target root gain is the root-normalized `Q_H` reward family.
"""

_BRANCHING_INFO = """
Branching rows show the selected action per rollout step: policy, chain, branch factor, beam width, selected strategy, selected position family, mixture component, sampler probability, and selection entropy.
"""

_TREE_SUMMARY_INFO = """
Rollout-tree summaries aggregate the factual selected steps stored in `rollouts.zarr`.

- `policy`, `horizon`, `branch_factor`, `beam_width`, and `temperature` identify the rollout recipe.
- `step_label` is the rollout depth of the selected action.
- `selected_position`, `selected_strategy`, and `selected_mixture` show which sampling family produced selected actions.
- `selected_steps` counts how often that route occurred in the inspected store.
- Mean fanout, invalid fraction, selected probability, entropy, marginal RRI, and root gain expose diversity and selection collapse.

The store does not persist every unexpanded parent edge as a graph. These plots visualize observed selected-branch provenance, not a full search tree reconstruction.
"""

_SELECTED_DEPTH_INFO = """
Selected-depth rows are the persisted selected successor-view depth renders for each rollout step.

- One row should align with each `steps/step_row_id`.
- `candidate_row_id` must match `steps/selected_candidate_row_id`.
- Valid and finite pixel fractions expose broken renders without loading every dense array.
- Depth statistics are computed only for the filtered rows shown on this tab.
- The quicklook reads one selected step and downsamples it for interactive plotting.
"""

_MASK_INFO = """
Candidate masks are hard contracts: `actor_action` marks deployable actor choices, `oracle_label` marks rows with oracle labels, `q_train` marks finite-candidate training cells, and `selected` marks the rollout path.
"""

_TARGET_INFO = """
Target audit separates actor-visible target metadata from GT/evaluation label validity. Invalid targets remain diagnostics and masks; they are not low-RRI training labels.
"""

_GEOMETRY_INFO = """
Geometry diagnostics summarize persisted candidate motion and clearance fields: path collision, clearance, free-space margin, step length, height delta, backward motion, yaw change, target distance, and target bearing.
"""

_RERUN_INFO = """
Rerun launch uses the selected current-schema rollout row. Native launch opens the desktop viewer; web launch writes an `.rrd` and serves it through the configured ports.
"""

_CANDIDATE_TABLE_INFO = """
Candidate row fields:

- `candidate_row_id`: stable row id inside `candidates/`.
- `step_index`: rollout step that generated this candidate shell.
- `shell_index`: index in the full sampled shell before valid-row compaction.
- `selected`: whether the rollout policy selected this candidate.
- `actor_action`: whether the actor may choose this row after hard masks.
- `q_train`: whether this row has the labels and masks required for `Q_H` training.
- `target_rri`: target-specific oracle RRI label when available.
- `target_root_gain`: root-normalized rollout/Q_H reward when available.
- `scene_rri`: scene-level oracle RRI audit label when available.
- `strategy`: candidate-generation family decoded from `strategy_id`.
- `position`: candidate-center family decoded from `position_id`.
- `mixture`: mixture component id; component names are shown when persisted, otherwise `component_<id>`.
- motion/clearance fields: candidate-generation diagnostics aligned from `candidate_diagnostics/`.
"""


def render_stored_rollouts_panel() -> None:
    """Render persisted rollout-Zarr validation, summaries, and Rerun launch."""

    st.header("Stored Rollout Zarr")
    st.caption("Load a standalone rollouts.zarr store, validate row contracts, and open selected rows in Rerun.")
    _info_popover("stored rollouts", _STORED_ROLLOUTS_INFO)

    path_config = PathConfig()
    store_paths = discover_rollout_store_paths(path_config.offline_cache_dir)
    inventory_rows = rollout_store_inventory_rows(store_paths)

    store_path = _render_store_selection(path_config=path_config, inventory_rows=inventory_rows)
    _render_store_inventory(inventory_rows=inventory_rows, path_config=path_config)
    if store_path is None:
        st.info("No rollout store selected. Generate or select a `*.zarr` store to inspect rollout rows.")
        return

    selected_inventory = _inventory_row_for_path(inventory_rows, store_path)
    bundle = _load_selected_store_bundle(store_path)
    if bundle["reader"] is None:
        st.error(f"Selected store cannot be opened: {bundle['error']}")
        _render_selected_store_metadata(selected_inventory=selected_inventory, root_attrs={}, manifest={})
        return

    reader = bundle["reader"]
    validation = bundle["validation"]
    root_attrs = bundle["root_attrs"]
    manifest = bundle["manifest"]
    current_schema = bool(validation is not None and validation.ok)
    rerun_controls = _render_rerun_controls(path_config) if current_schema else None

    (
        tab_overview,
        tab_validation,
        tab_objectives,
        tab_branching,
        tab_selected_depth,
        tab_targets,
        tab_candidates,
        tab_geometry,
        tab_suspicious,
        tab_metadata,
    ) = st.tabs(
        [
            "Overview",
            "Validation",
            "Objectives",
            "Branching",
            "Selected Depth",
            "Targets",
            "Candidates",
            "Geometry",
            "Suspicious",
            "Metadata",
        ]
    )

    with tab_overview:
        _render_selected_store_overview(
            reader=reader,
            validation=validation,
            selected_inventory=selected_inventory,
            manifest=manifest,
        )

    with tab_validation:
        _render_selected_store_validation(validation=validation, selected_inventory=selected_inventory)

    with tab_objectives:
        if _render_current_schema_gate(current_schema):
            _info_popover("objective metrics", _OBJECTIVE_INFO)
            _render_stored_metric_dashboard(reader)
            _render_stored_step_dashboard(reader, include_objective_plots=True, include_branching_plots=False)

    with tab_branching:
        if _render_current_schema_gate(current_schema):
            _info_popover("branching provenance", _BRANCHING_INFO)
            _render_stored_step_dashboard(reader, include_objective_plots=False, include_branching_plots=True)
            _info_popover("rollout tree summary", _TREE_SUMMARY_INFO)
            _render_rollout_tree_summary(reader)

    with tab_selected_depth:
        if _render_current_schema_gate(current_schema):
            _info_popover("selected depth", _SELECTED_DEPTH_INFO)
            _render_selected_depth_tab(reader)

    with tab_targets:
        if _render_current_schema_gate(current_schema):
            _info_popover("target audit", _TARGET_INFO)
            _render_targets_tab(reader)

    with tab_candidates:
        if _render_current_schema_gate(current_schema):
            _info_popover("candidate masks", _MASK_INFO)
            _render_candidates_tab(reader)

    with tab_geometry:
        if _render_current_schema_gate(current_schema):
            _info_popover("geometry diagnostics", _GEOMETRY_INFO)
            _render_geometry_tab(reader)

    with tab_suspicious:
        if _render_current_schema_gate(current_schema):
            config_path = rerun_controls[0] if rerun_controls is not None else path_config.resolve_under_root("")
            _render_suspicious_tab(reader, store_path=store_path, config_path=config_path)

    with tab_metadata:
        _render_selected_store_metadata(
            selected_inventory=selected_inventory,
            root_attrs=root_attrs,
            manifest=manifest,
        )

    if not current_schema:
        return

    if rerun_controls is None:
        return
    config_path, save_dir, web_viewer_port, ws_server_port = rerun_controls
    _render_rollout_row_table_and_rerun(
        reader=reader,
        store_path=store_path,
        config_path=config_path,
        save_dir=save_dir,
        web_viewer_port=web_viewer_port,
        ws_server_port=ws_server_port,
    )


def _render_store_selection(
    *,
    path_config: PathConfig,
    inventory_rows: list[dict[str, object]],
) -> Path | None:
    st.subheader("Rollout Stores")
    _info_popover("store discovery", _STORE_DISCOVERY_INFO)
    st.caption(f"Discovery root: `{path_config.offline_cache_dir}`")
    selected_from_inventory: Path | None = None
    if inventory_rows:
        selected_row = st.selectbox(
            "rollouts.zarr store",
            options=inventory_rows,
            format_func=lambda row: format_rollout_store_option(row, root=path_config.root),
            key="rollout_store_selector",
        )
        selected_from_inventory = Path(str(selected_row["path"])).expanduser().resolve()
    else:
        st.info("No `*.zarr` rollout stores were found under the configured offline cache directory.")

    with st.expander("Manual store override", expanded=not inventory_rows):
        manual_value = st.text_input(
            "Manual rollouts.zarr path",
            value="",
            key="rollout_store_manual_path",
            help="Absolute paths are used as-is; relative paths resolve through PathConfig.resolve_cache_artifact_dir.",
        )
        if manual_value.strip():
            try:
                return path_config.resolve_cache_artifact_dir(manual_value.strip())
            except Exception as exc:  # pragma: no cover - UI guard
                _report_exception(exc, context="Failed to resolve manual rollout store path")
                return selected_from_inventory
    return selected_from_inventory


def _render_store_inventory(
    *,
    inventory_rows: list[dict[str, object]],
    path_config: PathConfig,
) -> None:
    _info_popover("schema status", _SCHEMA_VALIDATION_INFO)
    _info_popover("rollout counts", _COUNTS_INFO)
    _info_popover("store inventory fields", _STORE_INVENTORY_INFO)
    if not inventory_rows:
        return
    _render_inventory_health_metrics(inventory_rows)
    display_rows = [_inventory_display_row(row, root=path_config.root) for row in inventory_rows]
    st.dataframe(display_rows, width="stretch", hide_index=True)
    error_rows = [
        {
            "store": _relative_display_path(Path(str(row["path"])), root=path_config.root),
            "error": error,
        }
        for row in inventory_rows
        for error in row.get("validation_errors", [])
    ]
    if error_rows:
        with st.expander("Validation and open errors", expanded=False):
            st.dataframe(error_rows, width="stretch", hide_index=True)


def _render_inventory_health_metrics(inventory_rows: list[dict[str, object]]) -> None:
    current_valid = sum(
        1 for row in inventory_rows if row.get("schema_status") == "current" and bool(row.get("validation_ok") is True)
    )
    blocked = len(inventory_rows) - current_valid
    observed_rollouts = sum(int(row.get("observed_rollouts") or 0) for row in inventory_rows)
    observed_steps = sum(int(row.get("observed_steps") or 0) for row in inventory_rows)
    total_size = sum(int(row.get("size_bytes") or 0) for row in inventory_rows)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Discovered stores", len(inventory_rows))
    metric_cols[1].metric("Current valid stores", current_valid)
    metric_cols[2].metric("Blocked stores", blocked)
    metric_cols[3].metric("Observed R/S", f"{observed_rollouts}/{observed_steps}")
    st.caption(f"Total discovered rollout-store footprint: {_format_bytes(total_size)}")


def _inventory_display_row(row: dict[str, object], *, root: Path) -> dict[str, object]:
    path = Path(str(row["path"]))
    return {
        "store": _relative_display_path(path, root=root),
        "schema": row.get("schema_status"),
        "schema_version": row.get("schema_version"),
        "validation": _validation_label(row.get("validation_ok")),
        "observed_rollouts": row.get("observed_rollouts"),
        "observed_steps": row.get("observed_steps"),
        "observed_candidates": row.get("observed_candidates"),
        "validator_rollouts": row.get("validator_rollouts"),
        "actor_action_fraction": _format_fraction(row.get("actor_action_fraction")),
        "q_train_fraction": _format_fraction(row.get("q_train_fraction")),
        "policies": row.get("policy_summary"),
        "horizons": row.get("horizon_summary"),
        "branch_factors": row.get("branch_factor_summary"),
        "manifest": row.get("manifest_schema_version"),
        "profile": row.get("manifest_profile"),
        "config": row.get("manifest_config"),
        "missing_groups": row.get("required_groups_missing"),
        "size": _format_bytes(row.get("size_bytes")),
        "files": row.get("file_count"),
        "first_error": row.get("first_error"),
    }


def _inventory_row_for_path(rows: list[dict[str, object]], store_path: Path) -> dict[str, object]:
    resolved = store_path.expanduser().resolve().as_posix()
    for row in rows:
        if str(row.get("path")) == resolved:
            return row
    fallback = rollout_store_inventory_rows([store_path])
    return fallback[0] if fallback else {"path": resolved, "name": store_path.name}


def _load_selected_store_bundle(store_path: Path) -> dict[str, object]:
    try:
        reader = RolloutZarrStoreReader(store_path)
    except Exception as exc:
        return {
            "reader": None,
            "validation": None,
            "root_attrs": {},
            "manifest": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    root_attrs = dict(reader.root.attrs)
    try:
        validation = reader.validate()
    except Exception as exc:
        validation = None
        validation_error = f"{type(exc).__name__}: {exc}"
    else:
        validation_error = ""
    try:
        manifest = reader.manifest()["manifest"]
    except Exception:
        manifest = {}
    return {
        "reader": reader,
        "validation": validation,
        "root_attrs": root_attrs,
        "manifest": manifest,
        "error": validation_error,
    }


def _render_selected_store_overview(
    *,
    reader: RolloutZarrStoreReader,
    validation: object,
    selected_inventory: dict[str, object],
    manifest: dict[str, object],
) -> None:
    metric_cols = st.columns(4)
    metric_cols[0].metric("Rollouts", _count_metric(validation, selected_inventory, "rollouts"))
    metric_cols[1].metric("Steps", _count_metric(validation, selected_inventory, "steps"))
    metric_cols[2].metric("Candidates", _count_metric(validation, selected_inventory, "candidates"))
    metric_cols[3].metric("Validation", "OK" if getattr(validation, "ok", False) else "FAILED")
    if getattr(validation, "ok", False):
        st.success("Store validation passed.")
        _render_rollout_store_summaries(reader, manifest=manifest)
    else:
        st.warning(
            "This store is not compatible with the current deep-inspection schema. Overview, validation, and metadata "
            "remain available; regenerate the shard before using candidate/Q_H deep tabs or Rerun launch."
        )
        if selected_inventory.get("first_error"):
            st.error(str(selected_inventory["first_error"]))


def _render_selected_store_validation(*, validation: object, selected_inventory: dict[str, object]) -> None:
    _info_popover("schema validation", _SCHEMA_VALIDATION_INFO)
    rows = [
        {"field": "schema_status", "value": _display_value(selected_inventory.get("schema_status"))},
        {"field": "schema_version", "value": _display_value(selected_inventory.get("schema_version"))},
        {
            "field": "required_groups_present",
            "value": _display_value(selected_inventory.get("required_groups_present")),
        },
        {
            "field": "required_groups_missing",
            "value": _display_value(selected_inventory.get("required_groups_missing")),
        },
        {"field": "observed_rollouts", "value": _display_value(selected_inventory.get("observed_rollouts"))},
        {"field": "observed_steps", "value": _display_value(selected_inventory.get("observed_steps"))},
        {"field": "observed_candidates", "value": _display_value(selected_inventory.get("observed_candidates"))},
        {"field": "validator_rollouts", "value": _display_value(selected_inventory.get("validator_rollouts"))},
        {"field": "validator_steps", "value": _display_value(selected_inventory.get("validator_steps"))},
        {"field": "validator_candidates", "value": _display_value(selected_inventory.get("validator_candidates"))},
    ]
    st.dataframe(rows, width="stretch", hide_index=True)
    missing = selected_inventory.get("missing_required_groups") or []
    if missing:
        st.markdown("**Missing required groups**")
        st.dataframe([{"group": group} for group in missing], width="stretch", hide_index=True)
    errors = list(getattr(validation, "errors", []) or selected_inventory.get("validation_errors", []) or [])
    if errors:
        st.markdown("**Validation errors**")
        st.dataframe([{"error": error} for error in errors], width="stretch", hide_index=True)
    else:
        st.success("No validation errors were reported.")


def _render_selected_store_metadata(
    *,
    selected_inventory: dict[str, object],
    root_attrs: dict[str, object],
    manifest: dict[str, object],
) -> None:
    st.markdown("**Inventory row**")
    st.json(selected_inventory)
    with st.expander("Root metadata", expanded=False):
        st.json(root_attrs)
    with st.expander("Generation manifest", expanded=False):
        st.json(manifest)


def _render_current_schema_gate(current_schema: bool) -> bool:
    if current_schema:
        return True
    st.info("This tab requires a store that passes the current rollout Zarr validation schema.")
    return False


def _render_rerun_controls(path_config: PathConfig) -> tuple[Path, Path, int, int]:
    _info_popover("rerun launch", _RERUN_INFO)
    try:
        default_config = path_config.resolve_config_toml_path("rerun_offline.toml", must_exist=True)
    except Exception:
        default_config = path_config.resolve_under_root(".configs/rerun_offline.toml")
    default_save = path_config.resolve_run_dir(".artifacts/rerun")
    config_path = path_config.resolve_config_toml_path(
        st.text_input("Rerun inspector config", value=str(default_config), key="rollout_rerun_config_path"),
        must_exist=False,
    )
    web_col1, web_col2, web_col3 = st.columns(3)
    web_viewer_port = int(
        web_col1.number_input("Rerun web-viewer port", min_value=0, max_value=65535, value=9090, step=1)
    )
    ws_server_port = int(
        web_col2.number_input("Rerun gRPC/proxy port", min_value=0, max_value=65535, value=9877, step=1)
    )
    save_dir = path_config.resolve_run_dir(web_col3.text_input("RRD save directory", value=str(default_save)))
    return config_path, save_dir, web_viewer_port, ws_server_port


def _render_rollout_row_table_and_rerun(
    *,
    reader: RolloutZarrStoreReader,
    store_path: Path,
    config_path: Path,
    save_dir: Path,
    web_viewer_port: int,
    ws_server_port: int,
) -> None:
    st.subheader("Selected Rollout Row")
    rollout_ids = reader.array("rollouts/rollout_row_id").astype(int).tolist()
    if not rollout_ids:
        st.info("No rollout rows are present.")
        return
    selected_rollout = int(
        st.selectbox(
            "Rollout row",
            options=rollout_ids,
            format_func=lambda row_id: format_rollout_option(reader, row_id),
            key="rollout_row_selector",
        )
    )
    _info_popover("rollout candidate rows", _CANDIDATE_TABLE_INFO)
    st.dataframe(candidate_rows_for_rollout(reader, selected_rollout), width="stretch", hide_index=True)

    native_command = build_rerun_rollout_spawn_command(
        config_path=config_path,
        rollout_store=store_path,
        rollout_row_id=selected_rollout,
    )
    save_path = save_dir / f"rollout_row_{selected_rollout}.rrd"
    web_command = build_rerun_rollout_web_command(
        config_path=config_path,
        rollout_store=store_path,
        rollout_row_id=selected_rollout,
        save_path=save_path,
        web_viewer_port=web_viewer_port,
        ws_server_port=ws_server_port,
        lan=True,
    )
    launch_col1, launch_col2 = st.columns(2)
    with launch_col1:
        st.markdown("**Native Rerun**")
        st.code(format_command(native_command), language="bash")
        if st.button("Open in Native Rerun", key="rollout_open_native_rerun"):
            _spawn_rerun_command(native_command, success_prefix="Spawned native Rerun inspector")
    with launch_col2:
        st.markdown("**Rerun Web Viewer**")
        st.code(format_command(web_command), language="bash")
        st.caption(f"Expected URL: {rerun_web_url(web_viewer_port=web_viewer_port, lan=True)}")
        if st.button("Open in Rerun Web Viewer", key="rollout_open_web_rerun"):
            save_path.parent.mkdir(parents=True, exist_ok=True)
            _spawn_rerun_command(web_command, success_prefix="Started Rerun web viewer")


def _spawn_rerun_command(command: list[str], *, success_prefix: str) -> None:
    try:
        process = spawn_background_command(command)
    except Exception as exc:  # pragma: no cover - UI guard
        _report_exception(exc, context="Failed to launch Rerun inspector")
    else:
        st.success(f"{success_prefix} with pid {process.pid}.")


def _render_rollout_store_summaries(reader: RolloutZarrStoreReader, *, manifest: dict[str, object]) -> None:
    target_rows = reader.array("targets/target_row_id")
    rollout_rows = reader.array("rollouts/rollout_row_id")
    step_rows = reader.array("steps/step_row_id")
    candidate_rows = reader.array("candidates/candidate_row_id")
    q_h = reader.q_h_view()
    q_train = q_h["q_train_mask"]
    valid_action = q_h["valid_action_mask"]
    actor_action = reader.array("candidates/actor_action_mask")
    oracle_label = reader.array("candidates/oracle_label_mask")
    summary = [
        {"table": "targets", "rows": int(target_rows.shape[0])},
        {"table": "rollouts", "rows": int(rollout_rows.shape[0])},
        {"table": "steps", "rows": int(step_rows.shape[0])},
        {"table": "candidates", "rows": int(candidate_rows.shape[0])},
        {"table": "actor_action candidates", "rows": int(actor_action.sum())},
        {"table": "oracle_label candidates", "rows": int(oracle_label.sum())},
        {"table": "q_h valid actions", "rows": int(valid_action.sum())},
        {"table": "q_h train cells", "rows": int(q_train.sum())},
    ]
    st.dataframe(summary, width="stretch", hide_index=True)
    coverage = manifest.get("source_coverage", {})
    if isinstance(coverage, dict) and coverage:
        st.markdown("**Source coverage**")
        st.json(coverage)
    target_summary = []
    target_valid = reader.array("targets/target_valid_mask")
    gt_valid = reader.array("targets/gt_label_valid_mask")
    for row_id, valid, gt_label in zip(target_rows, target_valid, gt_valid, strict=True):
        target_summary.append(
            {
                "target_row_id": int(row_id),
                "target_valid": bool(valid),
                "gt_label_valid": bool(gt_label),
            }
        )
    if target_summary:
        st.dataframe(target_summary, width="stretch", hide_index=True)


def _render_stored_metric_dashboard(reader: RolloutZarrStoreReader) -> None:
    rows = _stored_rollout_metric_rows(reader)
    if rows.empty:
        st.info("No rollout-level metrics are available in this store.")
        return

    finite_target = rows["final_cumulative_target_rri"].dropna()
    finite_scene = rows["final_cumulative_scene_rri"].dropna()
    metric_cols = st.columns(4)
    metric_cols[0].metric("Mean final target RRI", _format_metric(finite_target.mean()))
    metric_cols[1].metric("Best final target RRI", _format_metric(finite_target.max()))
    metric_cols[2].metric("Mean final scene RRI", _format_metric(finite_scene.mean()))
    metric_cols[3].metric("Q-train candidates", int(reader.array("candidates/q_train_mask").sum()))

    st.caption(
        "Endpoint `J_e^(H)` and log-gain require persisted target point-mesh before/after fields; current stores only persist cumulative RRI."
    )
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(
            px.histogram(rows, x="final_cumulative_target_rri", color="policy", title="Final cumulative target RRI"),
            width="stretch",
        )
    with chart_col2:
        grouped = rows.groupby(["policy", "horizon"], dropna=False)["final_cumulative_target_rri"].mean().reset_index()
        st.plotly_chart(
            px.bar(
                grouped,
                x="policy",
                y="final_cumulative_target_rri",
                color="horizon",
                barmode="group",
                title="Mean final target RRI by policy and horizon",
            ),
            width="stretch",
        )


def _render_stored_step_dashboard(
    reader: RolloutZarrStoreReader,
    *,
    include_objective_plots: bool = True,
    include_branching_plots: bool = True,
) -> None:
    rows = pd.DataFrame(rollout_step_objective_rows(reader))
    if rows.empty:
        st.info("No per-step rollout objective rows are available in this store.")
        return

    st.caption(
        "Marginal target RRI is the step-to-step difference of cumulative target RRI; "
        "selected target RRI is the selected candidate's one-step oracle label."
    )
    rows["rollout_chain"] = rows.apply(
        lambda row: f"row {int(row['rollout_row_id'])} / chain {int(row['chain_id'])}",
        axis=1,
    )
    display_cols = [
        "rollout_row_id",
        "chain_id",
        "policy",
        "step_index",
        "cumulative_target_rri",
        "marginal_target_rri",
        "selected_target_rri",
        "selected_target_root_gain",
        "selected_probability",
        "selected_entropy",
        "num_valid_candidates",
        "invalid_fraction",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
    ]
    _info_popover(
        "selected step table",
        "Selected-step rows are one factual action per rollout depth. They join persisted `steps/` arrays with the selected candidate row so objective deltas, fanout, invalidity, and sampling provenance can be inspected together.",
    )
    st.dataframe(rows[[col for col in display_cols if col in rows.columns]], width="stretch", hide_index=True)

    if not include_objective_plots and not include_branching_plots:
        return
    if include_objective_plots:
        _render_step_objective_plots(rows)
    if include_branching_plots:
        _render_step_branching_plots(rows)


def _render_step_objective_plots(rows: pd.DataFrame) -> None:
    _info_popover(
        "objective plots",
        "`Cumulative Target RRI` traces the selected path total by depth. `Marginal Target RRI` is the per-step delta, useful for spotting flat rewards, negative increments, or late-step collapse.",
    )
    objective_col, marginal_col = st.columns(2)
    with objective_col:
        st.plotly_chart(
            px.line(
                rows,
                x="step_index",
                y="cumulative_target_rri",
                color="rollout_chain",
                line_dash="policy",
                markers=True,
                hover_data=["target_row_id", "selected_target_rri", "selected_target_root_gain"],
                title="Cumulative Target RRI by Step",
            ),
            width="stretch",
        )
    with marginal_col:
        st.plotly_chart(
            px.bar(
                rows,
                x="step_index",
                y="marginal_target_rri",
                color="rollout_chain",
                facet_col="policy" if rows["policy"].nunique(dropna=True) > 1 else None,
                hover_data=["selected_target_rri", "selected_target_root_gain"],
                title="Marginal Target RRI by Step",
            ),
            width="stretch",
        )


def _render_step_branching_plots(rows: pd.DataFrame) -> None:
    _info_popover(
        "branching plots",
        "Branching diagnostics compare selected-action probability/entropy, valid fanout, invalid fraction, and selected sampling families across rollout depth. Use them to detect policy determinism, low diversity, and candidate-family imbalance.",
    )
    diagnostics_col, fanout_col = st.columns(2)
    with diagnostics_col:
        probability_rows = rows[rows["selected_probability"].notna() | rows["selected_entropy"].notna()]
        if probability_rows.empty:
            st.info("Selection probability/entropy fields are absent for these rows.")
        else:
            probability_long = probability_rows.melt(
                id_vars=["rollout_chain", "step_index"],
                value_vars=["selected_probability", "selected_entropy"],
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            st.plotly_chart(
                px.line(
                    probability_long,
                    x="step_index",
                    y="value",
                    color="metric",
                    line_dash="rollout_chain",
                    markers=True,
                    title="Selected-Action Probability and Entropy",
                ),
                width="stretch",
            )
    with fanout_col:
        fanout_long = rows.melt(
            id_vars=["rollout_chain", "step_index"],
            value_vars=["num_candidates", "num_valid_candidates", "invalid_fraction"],
            var_name="metric",
            value_name="value",
        ).dropna(subset=["value"])
        st.plotly_chart(
            px.line(
                fanout_long,
                x="step_index",
                y="value",
                color="metric",
                line_dash="rollout_chain",
                markers=True,
                title="Candidate Fanout and Invalid Fraction",
            ),
            width="stretch",
        )

    provenance_cols = ["policy", "selected_position", "selected_strategy", "selected_mixture"]
    provenance = (
        rows.groupby(provenance_cols, dropna=False)
        .size()
        .reset_index(name="selected_steps")
        .sort_values(["policy", "selected_steps"], ascending=[True, False])
    )
    st.plotly_chart(
        px.bar(
            provenance,
            x="selected_position",
            y="selected_steps",
            color="selected_strategy",
            facet_col="policy" if provenance["policy"].nunique(dropna=True) > 1 else None,
            hover_data=["selected_mixture"],
            title="Selected Sampling Families by Policy",
        ),
        width="stretch",
    )


def _render_rollout_tree_summary(reader: RolloutZarrStoreReader) -> None:
    rows = pd.DataFrame(rollout_tree_summary_rows(reader))
    if rows.empty:
        st.info("No selected rollout-tree provenance rows are available in this store.")
        return

    display_cols = [
        "policy",
        "horizon",
        "branch_factor",
        "beam_width",
        "temperature",
        "step_label",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
        "selected_steps",
        "mean_valid_fanout",
        "mean_invalid_fraction",
        "mean_marginal_target_rri",
        "mean_selected_target_root_gain",
        "mean_selected_probability",
        "mean_selected_entropy",
    ]
    st.dataframe(rows[[col for col in display_cols if col in rows.columns]], width="stretch", hide_index=True)

    tree_col, metric_col = st.columns(2)
    with tree_col:
        st.plotly_chart(
            px.sunburst(
                rows,
                path=["policy", "step_label", "selected_position", "selected_strategy", "selected_mixture"],
                values="selected_steps",
                color="mean_selected_target_root_gain",
                title="Observed Selected-Branch Provenance",
            ),
            width="stretch",
        )
    with metric_col:
        metric_rows = rows.melt(
            id_vars=["policy", "step_label", "selected_position", "selected_strategy"],
            value_vars=["mean_valid_fanout", "mean_invalid_fraction", "mean_selected_entropy"],
            var_name="metric",
            value_name="value",
        ).dropna(subset=["value"])
        st.plotly_chart(
            px.line(
                metric_rows,
                x="step_label",
                y="value",
                color="metric",
                line_dash="policy",
                markers=True,
                hover_data=["selected_position", "selected_strategy"],
                title="Tree Validity and Selection Diagnostics by Step",
            ),
            width="stretch",
        )

    family_rows = (
        rows.groupby(["step_label", "selected_position", "selected_strategy"], dropna=False)
        .agg(
            selected_steps=("selected_steps", "sum"),
            mean_target_root_gain=("mean_selected_target_root_gain", "mean"),
            mean_marginal_target_rri=("mean_marginal_target_rri", "mean"),
        )
        .reset_index()
    )
    st.plotly_chart(
        px.bar(
            family_rows,
            x="step_label",
            y="selected_steps",
            color="selected_position",
            pattern_shape="selected_strategy",
            hover_data=["mean_target_root_gain", "mean_marginal_target_rri"],
            title="Selected Candidate Families by Rollout Step",
        ),
        width="stretch",
    )


def _render_selected_depth_tab(reader: RolloutZarrStoreReader) -> None:
    row_limit = int(
        st.number_input(
            "Selected-depth row limit",
            min_value=1,
            max_value=10_000,
            value=128,
            step=32,
            key="stored_rollout_selected_depth_limit",
        )
    )
    rows = pd.DataFrame(selected_depth_summary_rows(reader, limit=row_limit))
    if rows.empty:
        st.info("No rollout steps are available for selected-depth inspection.")
        return

    metric_cols = st.columns(4)
    available = rows["available"].astype(bool) if "available" in rows else pd.Series(dtype=bool)
    metric_cols[0].metric("Selected-depth rows", len(rows))
    metric_cols[1].metric("Available rows", int(available.sum()) if not available.empty else 0)
    finite_fraction = rows["finite_fraction"].dropna() if "finite_fraction" in rows else pd.Series(dtype=float)
    metric_cols[2].metric("Mean finite pixels", _format_fraction(finite_fraction.mean()))
    depth_mean = rows["depth_mean_m"].dropna() if "depth_mean_m" in rows else pd.Series(dtype=float)
    metric_cols[3].metric("Mean selected depth", _format_metric(depth_mean.mean()))

    display_cols = [
        "rollout_row_id",
        "step_index",
        "step_row_id",
        "candidate_row_id",
        "selected_candidate_row_id",
        "available",
        "valid_fraction",
        "finite_fraction",
        "depth_min_m",
        "depth_mean_m",
        "depth_max_m",
        "image_height",
        "image_width",
        "selected_position",
        "selected_strategy",
        "selected_mixture",
        "selected_target_root_gain",
        "warning",
    ]
    st.dataframe(rows[[col for col in display_cols if col in rows.columns]], width="stretch", hide_index=True)

    preview_rows = rows[rows["available"].astype(bool)] if "available" in rows else pd.DataFrame()
    if preview_rows.empty:
        warnings = rows["warning"].dropna().astype(str).loc[lambda values: values != ""]
        if not warnings.empty:
            st.warning(warnings.iloc[0])
        else:
            st.info("No selected-depth row is available for quicklook.")
        return

    step_options = preview_rows["step_row_id"].astype(int).tolist()
    selected_step = int(
        st.selectbox(
            "Selected-depth step",
            options=step_options,
            format_func=lambda step_id: _format_selected_depth_option(preview_rows, int(step_id)),
            key="stored_rollout_selected_depth_step",
        )
    )
    preview = selected_depth_preview(reader, step_row_id=selected_step, max_size=96)
    if not bool(preview.get("available")):
        st.warning(str(preview.get("warning") or "Selected-depth preview is unavailable."))
        return
    depth = np.asarray(preview["depth_m"], dtype=np.float32)
    finite = depth[np.isfinite(depth)]
    zmax = float(np.max(finite)) if finite.size else None
    st.plotly_chart(
        depth_grid(
            torch.as_tensor(depth[None, ...], dtype=torch.float32),
            titles=[f"step {selected_step} · candidate {preview['candidate_row_id']}"],
            max_cols=1,
            zmax=zmax,
        ),
        width="stretch",
    )
    metadata = {
        "step_row_id": preview["step_row_id"],
        "candidate_row_id": preview["candidate_row_id"],
        "image_size_hw": preview["image_size_hw"],
        "focal_px": preview["focal_px"],
        "principal_point_px": preview["principal_point_px"],
        "preview_stride": preview["stride"],
    }
    st.json(metadata, expanded=False)


def _format_selected_depth_option(rows: pd.DataFrame, step_row_id: int) -> str:
    matches = rows[rows["step_row_id"].astype(int) == int(step_row_id)]
    if matches.empty:
        return f"step {step_row_id}"
    row = matches.iloc[0]
    return (
        f"rollout {int(row['rollout_row_id'])} · step {int(row['step_index'])} · "
        f"candidate {int(row['candidate_row_id'])} · mean={_format_metric(row.get('depth_mean_m'))}m"
    )


def _render_targets_tab(reader: RolloutZarrStoreReader) -> None:
    targets = pd.DataFrame(target_audit_rows(reader))
    if targets.empty:
        st.info("No stored target rows are available.")
        return
    st.dataframe(targets, width="stretch", hide_index=True)
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(
            px.histogram(targets, x="gt_match_status", color="target_valid", title="GT Match Status"),
            width="stretch",
        )
    with chart_col2:
        if "effective_support" in targets and targets["effective_support"].notna().any():
            st.plotly_chart(
                px.scatter(
                    targets,
                    x="effective_support",
                    y="selection_score",
                    color="gt_match_status",
                    hover_data=["target_row_id", "class", "confidence"],
                    title="Stored Target Score Decomposition",
                ),
                width="stretch",
            )
        else:
            st.info("Support/visibility fields are absent in this store; regenerate with target audit fields.")


def _render_candidates_tab(reader: RolloutZarrStoreReader) -> None:
    waterfall = pd.DataFrame(validity_waterfall_rows(reader))
    st.markdown("**Validity waterfall**")
    st.dataframe(waterfall, width="stretch", hide_index=True)
    st.plotly_chart(
        px.bar(
            waterfall,
            x="stage",
            y="count",
            text="count",
            title="Candidate Validity Waterfall",
        ),
        width="stretch",
    )
    for group_by in ("position", "strategy", "mixture", "invalid_reason", "policy"):
        rows = candidate_group_summary_rows(reader, group_by=group_by)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        st.markdown(f"**By {group_by}**")
        st.dataframe(df, width="stretch", hide_index=True)
        st.plotly_chart(
            px.bar(
                df,
                x=group_by,
                y=["actor_valid", "q_train", "selected"],
                barmode="group",
                title=f"Candidate Counts by {group_by}",
            ),
            width="stretch",
        )


def _render_geometry_tab(reader: RolloutZarrStoreReader) -> None:
    row_limit = int(
        st.number_input(
            "Candidate audit row limit (0 = all)",
            min_value=0,
            max_value=5_000_000,
            value=50_000,
            step=10_000,
            key="stored_rollout_candidate_audit_limit",
        )
    )
    limit = None if row_limit <= 0 else row_limit
    audit_df = pd.DataFrame(candidate_audit_rows(reader, limit=limit))
    if audit_df.empty:
        st.info("No candidate audit rows are available.")
        return
    metric_options = [
        "motion_step_length_m",
        "motion_height_delta_m",
        "motion_backward_step_m",
        "motion_yaw_delta_deg",
        "mesh_distance_m",
        "path_min_clearance_m",
        "free_space_margin_m",
        "target_distance_m",
        "target_bearing_yaw_deg",
        "target_root_gain",
        "target_rri",
    ]
    available = [name for name in metric_options if name in audit_df.columns and audit_df[name].notna().any()]
    selected_metric = st.selectbox(
        "Geometry / label metric",
        options=available or metric_options[:1],
        key="stored_rollout_geometry_metric",
    )
    color_field = st.selectbox(
        "Color / split by",
        options=["position", "strategy", "mixture", "invalid_reason", "policy"],
        key="stored_rollout_geometry_color",
    )
    st.dataframe(audit_df.head(1000), width="stretch", hide_index=True)
    if selected_metric not in audit_df:
        return
    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.plotly_chart(
            px.histogram(
                audit_df,
                x=selected_metric,
                color=color_field,
                title=f"{selected_metric} Distribution",
            ),
            width="stretch",
        )
    with chart_col2:
        st.plotly_chart(
            px.density_heatmap(
                audit_df,
                x="step_index",
                y=selected_metric,
                nbinsx=32,
                nbinsy=64,
                title=f"{selected_metric} by Rollout Step",
            ),
            width="stretch",
        )


def _render_suspicious_tab(
    reader: RolloutZarrStoreReader,
    *,
    store_path: Path,
    config_path: Path,
) -> None:
    cfg_cols = st.columns(4)
    cfg = RolloutSuspiciousQueryConfig(
        min_valid_candidates=int(cfg_cols[0].number_input("Min valid fanout", 0, 256, 3, step=1)),
        dominant_invalid_fraction=float(cfg_cols[1].slider("Dominant invalid fraction", 0.0, 1.0, 0.8, step=0.05)),
        high_target_score=float(cfg_cols[2].slider("High target score", 0.0, 1.0, 0.5, step=0.05)),
        max_step_distance_m=float(cfg_cols[3].slider("Max selected step (m)", 0.1, 5.0, 1.25, step=0.05)),
    )
    suspicious = pd.DataFrame(suspicious_rollout_rows(reader, config=cfg))
    if suspicious.empty:
        st.success("No suspicious rows matched the current thresholds.")
        return
    st.dataframe(suspicious, width="stretch", hide_index=True)
    rollout_options = [
        int(value)
        for value in suspicious["rollout_row_id"].dropna().astype(int).drop_duplicates().sort_values().tolist()
    ]
    if not rollout_options:
        return
    rollout_row_id = int(
        st.selectbox(
            "Suspicious rollout to open",
            options=rollout_options,
            key="stored_rollout_suspicious_open",
        )
    )
    command = build_rerun_rollout_spawn_command(
        config_path=config_path,
        rollout_store=store_path,
        rollout_row_id=rollout_row_id,
    )
    st.code(format_command(command), language="bash")


def _stored_rollout_metric_rows(reader: RolloutZarrStoreReader) -> pd.DataFrame:
    policies = _string_list(reader, "dictionaries/policy")
    scenes = _string_list(reader, "dictionaries/scene")
    rollout_ids = reader.array("rollouts/rollout_row_id")
    policy_ids = reader.array("rollouts/policy_id")
    scene_ids = reader.array("rollouts/scene_id")
    target_rows = reader.array("rollouts/target_row_id")
    horizon = reader.array("rollouts/horizon")
    branch_factor = reader.array("rollouts/branch_factor")
    target_rri = reader.array("rollouts/final_cumulative_target_rri")
    scene_rri = reader.array("rollouts/final_cumulative_scene_rri")
    return pd.DataFrame(
        [
            {
                "rollout_row_id": int(row_id),
                "scene": _dict_value(scenes, int(scene_id)),
                "target_row_id": int(target_row),
                "policy": _dict_value(policies, int(policy_id)),
                "horizon": int(h),
                "branch_factor": int(b),
                "final_cumulative_target_rri": _finite_or_none(target),
                "final_cumulative_scene_rri": _finite_or_none(scene),
            }
            for row_id, scene_id, target_row, policy_id, h, b, target, scene in zip(
                rollout_ids,
                scene_ids,
                target_rows,
                policy_ids,
                horizon,
                branch_factor,
                target_rri,
                scene_rri,
                strict=True,
            )
        ]
    )


def candidate_rows_for_rollout(reader: RolloutZarrStoreReader, rollout_row_id: int) -> list[dict[str, object]]:
    """Return display rows for one rollout's full candidate table."""

    return candidate_audit_rows(reader, rollout_row_id=int(rollout_row_id))


def format_rollout_option(reader: RolloutZarrStoreReader, rollout_row_id: int) -> str:
    """Format a rollout-row selector label with source and rollout context."""

    rollout_rows = reader.array("rollouts/rollout_row_id")
    matches = np.nonzero(rollout_rows == int(rollout_row_id))[0]
    if matches.size != 1:
        return f"rollout {rollout_row_id}"
    index = int(matches[0])
    policies = _string_list(reader, "dictionaries/policy")
    scenes = _string_list(reader, "dictionaries/scene")
    policy = _dict_value(policies, int(reader.array("rollouts/policy_id")[index]))
    scene = _dict_value(scenes, int(reader.array("rollouts/scene_id")[index]))
    target_row = int(reader.array("rollouts/target_row_id")[index])
    chain = int(reader.array("rollouts/chain_id")[index])
    horizon = int(reader.array("rollouts/horizon")[index])
    branch_factor = int(reader.array("rollouts/branch_factor")[index])
    beam = _format_stored_beam_width(int(reader.array("rollouts/beam_width")[index]))
    return (
        f"{rollout_row_id} · scene {scene} · target {target_row} · {policy} · "
        f"chain {chain} · H={horizon} · B={branch_factor} · beam={beam}"
    )


def format_rollout_store_option(row: dict[str, object], *, root: Path) -> str:
    """Format one rollout-store selector option from an inventory row."""

    path = Path(str(row.get("path", "")))
    rel_path = _relative_display_path(path, root=root)
    validation = _validation_label(row.get("validation_ok"))
    rollouts = row.get("observed_rollouts")
    steps = row.get("observed_steps")
    candidates = row.get("observed_candidates")
    return (
        f"{rel_path} · {row.get('schema_status', 'unknown')} · {validation} · "
        f"R/S/C={_display_count(rollouts)}/{_display_count(steps)}/{_display_count(candidates)}"
    )


def _format_stored_beam_width(value: int) -> str:
    return "NaN" if int(value) < 0 else str(int(value))


def _string_list(reader: RolloutZarrStoreReader, path: str) -> list[str]:
    try:
        return json.loads(bytes(reader.array(path).tolist()).decode("utf-8"))
    except Exception:
        return []


def _dict_value(values: list[str], index: int) -> str:
    if index < 0 or index >= len(values):
        return ""
    return values[index]


def _finite_or_none(value: object) -> float | None:
    value_float = float(value)
    return value_float if np.isfinite(value_float) else None


def _format_metric(value: object) -> str:
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{value_float:.4f}" if np.isfinite(value_float) else "n/a"


def _format_fraction(value: object) -> str:
    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return "n/a"
    return f"{100.0 * value_float:.1f}%" if np.isfinite(value_float) else "n/a"


def _format_bytes(value: object) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(size):
        return "n/a"
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    unit_idx = 0
    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1
    return f"{size:.1f} {units[unit_idx]}" if unit_idx else f"{int(size)} {units[unit_idx]}"


def _relative_display_path(path: Path, *, root: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(root.expanduser().resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _validation_label(value: object) -> str:
    if value is True:
        return "OK"
    if value is False:
        return "FAILED"
    return "not run"


def _display_count(value: object) -> str:
    if value is None:
        return "?"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return "?"


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list | tuple | set):
        return ", ".join(str(item) for item in value)
    return str(value)


def _count_metric(validation: object, inventory: dict[str, object], name: str) -> str:
    validator_attr = f"num_{name}"
    validator_value = getattr(validation, validator_attr, None)
    if validator_value not in (None, 0):
        return _display_count(validator_value)
    return _display_count(inventory.get(f"observed_{name}"))


__all__ = [
    "candidate_rows_for_rollout",
    "format_rollout_option",
    "format_rollout_store_option",
    "render_stored_rollouts_panel",
]
