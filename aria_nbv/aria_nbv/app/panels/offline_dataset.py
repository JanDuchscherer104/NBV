"""Standalone diagnostics for immutable VIN offline datasets.

The module provides store discovery, schema and coverage summaries, tensor
block statistics, distribution plots, and bounded Rerun launch controls without
mutating persisted training data.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import torch

from ...configs import PathConfig
from ...data_handling import VinOfflineStoreConfig
from ...data_handling.vin_store.diagnostics import (
    VinOfflineCoverageStats,
    VinOfflineDatasetStats,
    collect_vin_offline_dataset_coverage,
    collect_vin_offline_dataset_stats,
)
from ...data_handling.vin_store.source import VinOfflineSourceConfig
from ...dataset_topology import build_dataset_topology
from ...lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ...rollouts.inspection import discover_rollout_store_paths
from ...rri_metrics.ordinal import RriOrdinalBinner
from ..rerun_launch import build_rerun_offline_spawn_command, format_command, repo_root, spawn_background_command
from .common import _offline_summary_rows, current_scientific_label, render_scientific_notation

_STATS_CACHE_KEY = "vin_offline_dataset_page_stats"
_COVERAGE_CACHE_KEY = "vin_offline_dataset_page_coverage"
_SECTIONS = ("Overview", "Content", "Runtime", "Details")


def _load_offline_store_from_toml(toml_path: Path) -> VinOfflineStoreConfig:
    """Return the immutable VIN store configured by an experiment TOML."""

    cfg = AriaNBVExperimentConfig.from_toml(toml_path)
    source = cfg.datamodule_config.source
    if not isinstance(source, VinOfflineSourceConfig):
        raise TypeError(
            f"Experiment config uses {type(source).__name__}; expected VinOfflineSourceConfig.",
        )
    return source.offline.store


def _resolve_store(
    *,
    source_mode: str,
    store_dir_text: str,
    toml_choice: str,
    paths: PathConfig,
) -> VinOfflineStoreConfig:
    """Resolve a store from sidebar controls."""

    if source_mode == "Experiment config TOML":
        if toml_choice == "(none)":
            raise ValueError("Select an experiment config TOML.")
        return _load_offline_store_from_toml(paths.configs_dir / toml_choice)
    return VinOfflineStoreConfig(store_dir=Path(store_dir_text).expanduser())


def _component_rows(stats: VinOfflineDatasetStats) -> list[dict[str, object]]:
    """Return RRI component summary rows."""

    return [{"component": name, **asdict(summary)} for name, summary in sorted(stats.rri_component_summaries.items())]


def _pose_rows(stats: VinOfflineDatasetStats) -> list[dict[str, object]]:
    """Return candidate-pose summary rows."""

    return [{"metric": name, **asdict(summary)} for name, summary in sorted(stats.candidate_pose_summaries.items())]


def _block_rows(stats: VinOfflineDatasetStats) -> list[dict[str, object]]:
    """Return manifest block diagnostics as table rows."""

    rows: list[dict[str, object]] = []
    for block in stats.block_diagnostics:
        rows.append(
            {
                "shard_id": block.shard_id,
                "name": block.name,
                "kind": block.kind,
                "dtype": block.dtype,
                "shape": block.shape,
                "optional": block.optional,
                "estimated_mib": (None if block.estimated_bytes is None else float(block.estimated_bytes) / (1024**2)),
            },
        )
    return rows


def _sample_rows(stats: VinOfflineDatasetStats) -> list[dict[str, object]]:
    """Return sampled per-row sanity summaries as table rows."""

    rows: list[dict[str, object]] = []
    for sample in stats.sample_summaries:
        rows.append(
            {
                "sample_index": sample.sample_index,
                "sample_key": sample.sample_key,
                "scene_id": sample.scene_id,
                "snippet_id": sample.snippet_id,
                "split": sample.split,
                "shard_id": sample.shard_id,
                "row": sample.row,
                "candidate_count": sample.candidate_count,
                "finite_rri_count": sample.rri.count,
                "rri_min": sample.rri.minimum,
                "rri_mean": sample.rri.mean,
                "rri_max": sample.rri.maximum,
                "vin_points_count": sample.vin_points.count,
                "vin_points_mean": sample.vin_points.mean,
            },
        )
    return rows


def _render_histogram(
    values: list[float],
    *,
    title: str,
    x_label: str,
    nbins: int,
    log_y: bool,
) -> None:
    """Render one Plotly histogram when values are available."""

    if not values:
        st.info(f"No values available for {title}.")
        return
    fig = px.histogram(
        x=values,
        nbins=int(nbins),
        title=title,
        labels={"x": x_label, "y": "count"},
    )
    if log_y:
        fig.update_yaxes(type="log")
    st.plotly_chart(fig, width="stretch")


def _render_rri_components(stats: VinOfflineDatasetStats, *, hist_bins: int, log_y: bool) -> None:
    """Render RRI component summaries and distributions."""

    rows = _component_rows(stats)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No RRI component blocks available.")
        return

    render_scientific_notation("rri", "point_to_mesh_error", "mesh_to_point_error")

    for name, values in sorted(stats.rri_component_values.items()):
        _render_histogram(
            values,
            title=f"{current_scientific_label(name)} Distribution",
            x_label=current_scientific_label(name),
            nbins=hist_bins,
            log_y=log_y,
        )

    if stats.rri_component_values.get("pm_comp_after") and stats.rri_values:
        count = min(len(stats.rri_values), len(stats.rri_component_values["pm_comp_after"]))
        fig = px.scatter(
            x=stats.rri_values[:count],
            y=stats.rri_component_values["pm_comp_after"][:count],
            labels={"x": current_scientific_label("rri"), "y": current_scientific_label("mesh_to_point_error")},
            title=f"{current_scientific_label('rri')} vs {current_scientific_label('mesh_to_point_error')}",
        )
        st.plotly_chart(fig, width="stretch")

    if stats.rri_component_values.get("pm_acc_after") and stats.rri_values:
        count = min(len(stats.rri_values), len(stats.rri_component_values["pm_acc_after"]))
        fig = px.scatter(
            x=stats.rri_values[:count],
            y=stats.rri_component_values["pm_acc_after"][:count],
            labels={"x": current_scientific_label("rri"), "y": current_scientific_label("point_to_mesh_error")},
            title=f"{current_scientific_label('rri')} vs {current_scientific_label('point_to_mesh_error')}",
        )
        st.plotly_chart(fig, width="stretch")


def _render_candidate_geometry(stats: VinOfflineDatasetStats, *, candidate_bins: int, log_y: bool) -> None:
    """Render candidate-pose geometry diagnostics."""

    rows = _pose_rows(stats)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No candidate pose blocks available.")
        return

    values = stats.candidate_pose_values
    azimuth = values.get("azimuth_deg", [])
    elevation = values.get("elevation_deg", [])
    if azimuth and elevation:
        fig = px.density_heatmap(
            x=azimuth,
            y=elevation,
            nbinsx=int(candidate_bins),
            nbinsy=int(candidate_bins),
            labels={"x": "azimuth_deg", "y": "elevation_deg"},
            title="Offset Azimuth/Elevation in Reference Rig Frame",
        )
        st.plotly_chart(fig, width="stretch")

    for name in (
        "radius_m",
        "azimuth_deg",
        "elevation_deg",
        "yaw_deg",
        "pitch_deg",
        "roll_deg",
        "rotation_delta_deg",
    ):
        _render_histogram(
            values.get(name, []),
            title=f"{name} Distribution",
            x_label=name,
            nbins=candidate_bins,
            log_y=log_y,
        )


def _render_batch_memory(stats: VinOfflineDatasetStats, *, log_y: bool) -> None:
    """Render batch-shape and memory diagnostics."""

    st.subheader("VIN Batch Shape Preview")
    if stats.batch_shapes:
        st.json(stats.batch_shapes, expanded=True)
    else:
        st.info("No batch shape preview available.")

    st.subheader("Estimated Runtime Memory")
    rows = [asdict(row) for row in stats.memory_diagnostics]
    if not rows:
        st.info("No memory diagnostics available.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)
    fig = px.bar(
        rows,
        x="component",
        y="mean_mib",
        title="Mean Estimated Runtime Memory by Component",
        labels={"mean_mib": "MiB"},
    )
    if log_y:
        fig.update_yaxes(type="log")
    st.plotly_chart(fig, width="stretch")


def _render_backbone(stats: VinOfflineDatasetStats, *, log_y: bool) -> None:
    """Render backbone numeric field diagnostics."""

    rows = [asdict(row) for row in stats.backbone_diagnostics]
    if not rows:
        st.info("No backbone numeric blocks available.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)
    plot_rows = sorted(rows, key=lambda row: float(row.get("std") or 0.0), reverse=True)[:16]
    fig = px.bar(
        plot_rows,
        x="std",
        y="field",
        orientation="h",
        title="Backbone Field Standard Deviation",
        labels={"std": "std"},
    )
    if log_y:
        fig.update_xaxes(type="log")
    st.plotly_chart(fig, width="stretch")


def _render_binner(stats: VinOfflineDatasetStats, *, binner_classes: int, hist_bins: int, log_y: bool) -> None:
    """Fit and render an offline RRI ordinal-binner preview."""

    if not stats.rri_values:
        st.info("No RRI values available to fit a binner.")
        return

    rri_tensor = torch.tensor(stats.rri_values, dtype=torch.float32)
    binner = RriOrdinalBinner.fit_from_iterable([rri_tensor], num_classes=int(binner_classes))
    labels = binner.transform(rri_tensor)
    counts = torch.bincount(labels.to(torch.int64), minlength=int(binner.num_classes)).cpu().numpy()
    edge_rows = [{"edge_index": idx, "edge": float(edge)} for idx, edge in enumerate(binner.edges.cpu().tolist())]
    count_rows = [{"class": idx, "count": int(count)} for idx, count in enumerate(counts.tolist())]

    col_l, col_r = st.columns(2)
    col_l.dataframe(edge_rows, width="stretch", hide_index=True)
    col_r.dataframe(count_rows, width="stretch", hide_index=True)

    fig = px.histogram(
        x=stats.rri_values,
        nbins=hist_bins,
        title=f"Raw {current_scientific_label('oracle_rri')} with Quantile Edges",
        labels={"x": current_scientific_label("oracle_rri"), "y": "count"},
    )
    if log_y:
        fig.update_yaxes(type="log")
    for edge in binner.edges.cpu().tolist():
        fig.add_vline(x=float(edge), line_width=1, line_dash="dot", opacity=0.35)
    st.plotly_chart(fig, width="stretch")

    fig_counts = px.bar(
        count_rows,
        x="class",
        y="count",
        title="Ordinal Label Counts",
        labels={"class": "class", "count": "count"},
    )
    if log_y:
        fig_counts.update_yaxes(type="log")
    st.plotly_chart(fig_counts, width="stretch")


def _render_coverage(coverage: VinOfflineCoverageStats | None) -> None:
    """Render raw-dataset coverage diagnostics."""

    if coverage is None:
        st.info("Click Scan dataset coverage to compare raw tar headers with the immutable store index.")
        return

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Dataset snippets", coverage.dataset_snippets)
    col_b.metric("Store snippets", coverage.store_snippets)
    col_c.metric("Covered", coverage.covered_snippets)
    col_d.metric("Coverage", "n/a" if coverage.coverage is None else f"{100.0 * coverage.coverage:.2f}%")

    col_e, col_f, col_g, col_h = st.columns(4)
    col_e.metric("Dataset scenes", coverage.dataset_scenes)
    col_f.metric("Store scenes", coverage.store_scenes)
    col_g.metric("Missing in store", coverage.missing_in_store)
    col_h.metric("Outside dataset", coverage.outside_dataset)
    st.caption(f"Tar shards scanned: {coverage.tar_shards_scanned}")

    if coverage.per_scene:
        st.dataframe([asdict(row) for row in coverage.per_scene], width="stretch", hide_index=True)
    if coverage.missing_examples:
        st.subheader("Missing in Store Examples")
        st.dataframe(
            [{"scene_id": scene, "snippet_id": snippet} for scene, snippet in coverage.missing_examples],
            width="stretch",
            hide_index=True,
        )
    if coverage.outside_examples:
        st.subheader("Outside Dataset Examples")
        st.dataframe(
            [{"scene_id": scene, "snippet_id": snippet} for scene, snippet in coverage.outside_examples],
            width="stretch",
            hide_index=True,
        )


def _render_stats(
    stats: VinOfflineDatasetStats,
    *,
    hist_bins: int,
    candidate_bins: int,
    binner_classes: int,
    log_y: bool,
    coverage: VinOfflineCoverageStats | None,
) -> None:
    """Render one collected immutable offline-store diagnostics object."""

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Samples", stats.num_samples)
    col_b.metric("Sampled rows", stats.sampled_samples)
    col_c.metric("Scenes", stats.num_scenes)
    col_d.metric("Numeric blocks", f"{stats.numeric_bytes / (1024**2):.1f} MiB")

    tab_overview, tab_content, tab_runtime, tab_details = st.tabs(list(_SECTIONS))

    with tab_overview:
        st.dataframe(_offline_summary_rows(stats), width="stretch", hide_index=True)
        col_l, col_r = st.columns(2)
        col_l.json(stats.split_counts, expanded=True)
        col_r.json(stats.materialized_blocks, expanded=True)
        _render_coverage(coverage)

    with tab_content:
        with st.expander("Core distributions", expanded=True):
            _render_histogram(
                stats.candidate_count_values,
                title="Valid Candidate Counts",
                x_label="candidate_count",
                nbins=hist_bins,
                log_y=log_y,
            )
            _render_histogram(
                stats.rri_values,
                title="Oracle RRI",
                x_label="rri",
                nbins=hist_bins,
                log_y=log_y,
            )
            _render_histogram(
                stats.vin_point_values,
                title="VIN Point Lengths",
                x_label="vin_points",
                nbins=hist_bins,
                log_y=log_y,
            )
        with st.expander("RRI components"):
            _render_rri_components(stats, hist_bins=hist_bins, log_y=log_y)
        with st.expander("Candidate geometry"):
            _render_candidate_geometry(stats, candidate_bins=candidate_bins, log_y=log_y)
        with st.expander("Backbone features"):
            _render_backbone(stats, log_y=log_y)

    with tab_runtime:
        _render_batch_memory(stats, log_y=log_y)

    with tab_details:
        with st.expander("Persisted blocks"):
            st.dataframe(_block_rows(stats), width="stretch", hide_index=True)
        with st.expander("Sample sanity"):
            st.dataframe(_sample_rows(stats), width="stretch", hide_index=True)
        with st.expander("RRI binning"):
            _render_binner(stats, binner_classes=binner_classes, hist_bins=hist_bins, log_y=log_y)
        with st.expander("Manifest and shapes"):
            st.json(
                {
                    "store_dir": stats.store_dir,
                    "version": stats.version,
                    "num_samples": stats.num_samples,
                    "sampled_samples": stats.sampled_samples,
                    "split_counts": stats.split_counts,
                    "materialized_blocks": stats.materialized_blocks,
                    "block_shapes": stats.block_shapes,
                    "batch_shapes": stats.batch_shapes,
                },
                expanded=False,
            )


def render_offline_dataset_page() -> None:
    """Render immutable VIN offline dataset diagnostics as a standalone page."""

    st.header("Root Observation Store")
    st.caption(
        "Inspect immutable VIN offline stores directly from their manifest and indexed shards.",
    )
    paths = PathConfig()
    config_paths = sorted(
        paths.configs_dir.glob("*.toml"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    with st.sidebar.form("vin_offline_dataset_form"):
        st.subheader("Root Observation Store")
        source_mode = st.radio(
            "Source",
            options=["Store directory", "Experiment config TOML"],
            index=0,
            key="vin_offline_dataset_source_mode",
        )
        store_dir_text = st.text_input(
            "Store directory",
            value=str(VinOfflineStoreConfig().store_dir),
            disabled=source_mode != "Store directory",
            key="vin_offline_dataset_store_dir",
        )
        toml_options = ["(none)"] + [path.name for path in config_paths]
        toml_choice = st.selectbox(
            "Experiment config TOML",
            options=toml_options,
            index=0,
            disabled=source_mode != "Experiment config TOML",
            key="vin_offline_dataset_toml",
        )
        max_samples = int(
            st.number_input(
                "Diagnostic sample limit",
                min_value=1,
                max_value=100000,
                value=512,
                step=128,
                key="vin_offline_dataset_sample_limit",
            ),
        )
        hist_bins = int(
            st.number_input(
                "Histogram bins",
                min_value=5,
                max_value=200,
                value=40,
                step=5,
                key="vin_offline_dataset_hist_bins",
            ),
        )
        candidate_bins = int(
            st.number_input(
                "Candidate geometry bins",
                min_value=10,
                max_value=240,
                value=60,
                step=5,
                key="vin_offline_dataset_candidate_bins",
            ),
        )
        binner_classes = int(
            st.number_input(
                "Binner classes",
                min_value=2,
                max_value=50,
                value=15,
                step=1,
                key="vin_offline_dataset_binner_classes",
            ),
        )
        max_tars = int(
            st.number_input(
                "Max tar shards for coverage (0 = all)",
                min_value=0,
                max_value=100000,
                value=0,
                step=1,
                key="vin_offline_dataset_max_tars",
            ),
        )
        log_y = st.checkbox("Log-scale histogram counts", value=False, key="vin_offline_dataset_log_y")
        rerun_config_text = st.text_input(
            "Rerun inspector config",
            value=str(repo_root() / ".configs" / "rerun_offline.toml"),
            key="vin_offline_dataset_rerun_config",
        )
        rerun_split = st.selectbox(
            "Rerun split",
            options=["all", "train", "val"],
            index=0,
            key="vin_offline_dataset_rerun_split",
        )
        rerun_index = int(
            st.number_input(
                "Rerun sample index",
                min_value=0,
                max_value=100000000,
                value=0,
                step=1,
                key="vin_offline_dataset_rerun_index",
            )
        )
        inspect = st.form_submit_button("Inspect offline store")
        scan_coverage = st.form_submit_button("Scan dataset coverage")
        launch_rerun = st.form_submit_button("Open sample in Rerun")

    try:
        store = _resolve_store(
            source_mode=source_mode,
            store_dir_text=store_dir_text,
            toml_choice=toml_choice,
            paths=paths,
        )
    except Exception as exc:
        if inspect or scan_coverage:
            st.error(f"Could not resolve VIN offline store: {type(exc).__name__}: {exc}")
        store = None

    workspace = st.segmented_control(
        "VIN inspection workspace",
        options=["Diagnostics", "Trust & Topology"],
        default="Diagnostics",
        key="vin_offline_dataset_workspace",
        width="stretch",
    )
    if workspace == "Trust & Topology":
        if store is None:
            st.info("Select a VIN store to resolve its artifact topology.")
            return
        _render_vin_topology(store=store, paths=paths)
        return

    if launch_rerun:
        try:
            if store is None:
                raise ValueError("No VIN offline store is selected.")
            command = build_rerun_offline_spawn_command(
                config_path=Path(rerun_config_text).expanduser(),
                offline_store=store.store_dir,
                split=str(rerun_split),
                index=int(rerun_index),
            )
            st.code(format_command(command), language="bash")
            process = spawn_background_command(command)
        except Exception as exc:  # pragma: no cover - UI guard
            st.error(f"Could not spawn Rerun inspector: {type(exc).__name__}: {exc}")
        else:
            st.success(f"Spawned Rerun inspector with pid {process.pid}.")

    stats_key = None
    coverage_key = None
    if store is not None:
        stats_key = f"{store.store_dir.expanduser().resolve().as_posix()}|{max_samples}"
        coverage_key = f"{store.store_dir.expanduser().resolve().as_posix()}|{max_tars}"

    if inspect or scan_coverage:
        try:
            if store is None:
                raise ValueError("No VIN offline store is selected.")
            if not store.manifest_path.is_file():
                raise FileNotFoundError(f"Missing VIN offline manifest: {store.manifest_path}")
            cached_stats = st.session_state.get(_STATS_CACHE_KEY)
            has_current_stats = isinstance(cached_stats, dict) and cached_stats.get("key") == stats_key
            if inspect or not has_current_stats:
                stats = collect_vin_offline_dataset_stats(store, max_samples=max_samples)
                st.session_state[_STATS_CACHE_KEY] = {
                    "key": stats_key,
                    "stats": stats,
                }
            if scan_coverage:
                progress = st.progress(0.0)

                def _progress(done: int, total: int) -> None:
                    progress.progress(1.0 if total <= 0 else min(1.0, float(done) / float(total)))

                coverage = collect_vin_offline_dataset_coverage(
                    store,
                    max_tars=None if max_tars <= 0 else max_tars,
                    progress_cb=_progress,
                )
                progress.empty()
                st.session_state[_COVERAGE_CACHE_KEY] = {
                    "key": coverage_key,
                    "coverage": coverage,
                }
        except Exception as exc:  # pragma: no cover - UI guard
            st.error(f"Could not inspect VIN offline store: {type(exc).__name__}: {exc}")
            if inspect:
                st.session_state.pop(_STATS_CACHE_KEY, None)
            if scan_coverage:
                st.session_state.pop(_COVERAGE_CACHE_KEY, None)

    cached = st.session_state.get(_STATS_CACHE_KEY)
    coverage_cached = st.session_state.get(_COVERAGE_CACHE_KEY)
    coverage = (
        coverage_cached.get("coverage")
        if isinstance(coverage_cached, dict) and coverage_cached.get("key") == coverage_key
        else None
    )
    if not cached or cached.get("key") != stats_key:
        if coverage is not None:
            _render_coverage(coverage)
        else:
            st.info("Choose a store and click Inspect offline store.")
        return

    _render_stats(
        cached["stats"],
        hist_bins=hist_bins,
        candidate_bins=candidate_bins,
        binner_classes=binner_classes,
        log_y=log_y,
        coverage=coverage,
    )


def _render_vin_topology(*, store: VinOfflineStoreConfig, paths: PathConfig) -> None:
    """Render the shared read-only artifact topology from the VIN page."""

    rollout_paths = discover_rollout_store_paths(paths.offline_cache_dir)
    options: list[Path | None] = [None, *rollout_paths]
    rollout_path = st.selectbox(
        "Rollout store to resolve against this VIN manifest",
        options=options,
        format_func=lambda value: "VIN only" if value is None else str(value),
        key="vin_topology_rollout_store",
    )
    try:
        topology = build_dataset_topology(
            rollout_store_dir=rollout_path,
            vin_store_dirs=[store.store_dir],
            path_config=paths,
        )
    except Exception as exc:
        st.error(f"Could not resolve dataset topology: {type(exc).__name__}: {exc}")
        return

    st.subheader("Trust & Topology")
    st.caption(
        "Manifest hashes and persisted identifiers determine links. Inferred paths, missing artifacts, and ambiguity remain explicit."
    )
    with st.popover("How to read the topology", icon="ℹ️"):
        st.markdown(
            """
**Question**

Which VIN, rollout, source, mesh, report, and Rerun artifacts are physically embedded or resolvable locally?

**Population / grain**

Artifact nodes and typed pointer edges. Source rows stay collapsed until drill-down.

**Metric / units**

Edge width is relationship count, not bytes, sample count, or scientific effect size.

**Denominator / masks**

All topology relationships recorded by the selected manifests and `PathConfig` resolution.

**Comparison conditions**

Compare resolution classes only. A wide node does not imply better data.

**Expected pattern**

Manifest hashes resolve uniquely and required modalities have a clear owner.

**Warnings / failures**

Missing and ambiguous links report incomplete local provenance; inferred paths are weaker than persisted pointers.

**Evidence role / sources**

Provenance from VIN and rollout manifests, sample indexes, configured roots, and mesh locations.
"""
        )
    sankey = topology.sankey_data()
    if sankey.get("link", {}).get("source"):
        fig = go.Figure(go.Sankey(node=sankey["node"], link=sankey["link"]))
        fig.update_layout(title="VIN, rollout, mesh, report, and Rerun artifact topology", height=500)
        st.plotly_chart(fig, width="stretch")
    modality_rows = topology.modality_rows()
    if modality_rows:
        st.dataframe(modality_rows, hide_index=True, width="stretch")
    with st.expander("Selected-source drill-down and Rich-compatible tree"):
        source_rows = topology.source_rows()
        if source_rows:
            source_id = st.selectbox(
                "Source row",
                options=[int(row["source_row_id"]) for row in source_rows],
                key="vin_topology_source_row",
            )
            topology = build_dataset_topology(
                rollout_store_dir=rollout_path,
                vin_store_dirs=[store.store_dir],
                path_config=paths,
                selected_source_row_id=int(source_id),
            )
            st.dataframe(
                [row for row in source_rows if int(row["source_row_id"]) == int(source_id)],
                hide_index=True,
                width="stretch",
            )
        st.code(topology.plain_text_tree(), language="text")
    payload = json.dumps(topology.to_jsonable(), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    st.download_button(
        "Download topology JSON",
        data=payload,
        file_name="vin-dataset-topology.json",
        mime="application/json",
    )


__all__ = ["render_offline_dataset_page"]
