"""Store selection, trust, and topology section."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....configs import PathConfig
from ....dataset_topology import build_native_dataset_layout, discover_vin_store_dirs
from ....dataset_topology.rendering import render_topology_snapshot
from .session import StoredRolloutSession, clear_stored_rollout_caches
from .shared import (
    _ROLE_COLORS,
    _download_frame,
    _download_json,
    _info_popover,
    _render_plot,
)

_OVERVIEW_INFO = """
This section establishes whether the selected artifact can support later claims.

- **Currentness:** schema validation checks persisted structure, row linkage, masks, and required provenance. A stale store remains inspectable as metadata but cannot support scientific plots or Rerun claims.
- **Provenance:** topology edges distinguish embedded payloads, resolved pointers, inferred paths, and missing links. Edge width is a relationship count, not data volume or effect size.
- **Roles:** actor-visible inputs, privileged oracle/evaluation data, derived training views, and provenance are separate evidence classes.
- **Reference coverage:** source scenes and unique snippet windows are shown against the full 100-scene, 4,608-window GT-mesh ASE target. This scale footprint is distinct from an exact raw-tar membership audit.
- **Physical footprint:** on-disk Zarr bytes and bytes per rollout, step, and candidate describe storage cost; they are distinct from robot acquisition cost.

Healthy stores have one resolvable owner for required modalities and exact source hashes. Missing or ambiguous links indicate incomplete local provenance; they do not silently invalidate or repair numeric values.
"""


def _render_store_selector(paths: PathConfig, inventory: list[dict[str, object]]) -> Path | None:
    """Render compact store selection without materializing candidate evidence."""

    col_store, col_status = st.columns([4, 1])
    selected: Path | None = None
    if inventory:
        row = col_store.selectbox(
            "rollouts.zarr store",
            options=inventory,
            format_func=lambda item: (
                f"{Path(str(item['path'])).name} · {item.get('schema_status', 'unknown')} · "
                f"R/S/C={item.get('observed_rollouts', '?')}/{item.get('observed_steps', '?')}/"
                f"{item.get('observed_candidates', '?')}"
            ),
            key="rollout_store_selector",
        )
        selected = Path(str(row["path"])).expanduser().resolve()
        col_status.metric("Schema", str(row.get("schema_status", "unknown")).upper())
    else:
        col_store.info(f"No `*.zarr` rollout stores found below `{paths.offline_cache_dir}`.")

    with st.expander("Store path override", expanded=not inventory):
        manual = st.text_input("Manual rollouts.zarr path", value="", key="rollout_store_manual_path")
        if manual.strip():
            candidate = Path(manual).expanduser()
            if not candidate.is_absolute():
                candidate = paths.resolve_cache_artifact_dir(manual)
            selected = candidate.resolve()
    if col_status.button("Refresh stores", help="Clear inspector caches after creating or replacing a store."):
        clear_stored_rollout_caches()
        st.rerun()
    return selected


def _render_role_legend() -> None:
    badges = " ".join(
        f'<span style="display:inline-block;padding:.15rem .45rem;margin:.1rem;border-radius:.35rem;'
        f'background:{color};color:white;font-size:.78rem">{html.escape(role)}</span>'
        for role, color in _ROLE_COLORS.items()
    )
    st.markdown(
        "**Evidence roles:** "
        + badges
        + "<br><span style='font-size:.85rem'>Actor-visible inputs, privileged evaluation, derived training caches, "
        "and provenance are never interchangeable.</span>",
        unsafe_allow_html=True,
    )


def _render_header_metrics(summary: dict[str, object], *, validation_ok: bool) -> None:
    """Render selected-store evidence in source, task, and rollout domains."""

    st.markdown("#### Store Contract")
    contract = st.columns(4)
    contract[0].metric("Validation", "OK" if validation_ok else "BLOCKED")
    contract[1].metric("Target Protocol", _header_metric_value(summary.get("target_protocol")))
    contract[2].metric("Planning Horizon", _header_metric_value(summary.get("horizon")))
    contract[3].metric("QH Return", _q_h_return_value(summary))

    source, targets, rollouts = st.columns(3)
    with source:
        with st.container(border=True):
            st.markdown("##### Source Cohort")
            st.caption("Which persisted snippets and scenes supplied the rollout roots.")
            first, second = st.columns(2)
            first.metric("Source Scenes", _header_metric_value(summary.get("source_scenes")))
            second.metric("Source Rows", _header_metric_value(summary.get("source_rows")))
            st.metric(
                "Source Snippets / Scene (Min/Median/Max)",
                _header_distribution_value(summary.get("snippets_per_scene")),
            )
            source_value, source_delta = _split_metric(summary.get("source_split_counts"))
            st.metric("Source Split (Train/Val/Test)", source_value, delta=source_delta, delta_color="off")

    with targets:
        with st.container(border=True):
            st.markdown("##### Target Task Coverage")
            st.caption("Persisted target tasks, their actor-validity, and whether they have factual rollout evidence.")
            first, second = st.columns(2)
            first.metric("Persisted Target Tasks", _header_metric_value(summary.get("target_tasks")))
            second.metric(
                "Actor-Valid Target Tasks",
                _header_coverage_value(summary.get("actor_valid_targets"), summary.get("target_tasks")),
            )
            st.metric(
                "Actor-Valid Tasks with Rollouts",
                _header_coverage_value(
                    summary.get("actor_valid_targets_with_rollouts"), summary.get("actor_valid_targets")
                ),
            )
            st.metric(
                "Target Tasks / Represented Scene (Min/Median/Max)",
                _header_distribution_value(summary.get("target_tasks_per_scene")),
            )
            st.metric(
                "Actor-Valid Target Tasks / Represented Scene (Min/Median/Max)",
                _header_distribution_value(summary.get("actor_valid_targets_per_scene")),
            )
            st.metric(
                "Actor-Valid Tasks with Rollouts / Scene (Min/Median/Max)",
                _header_distribution_value(summary.get("actor_valid_targets_with_rollouts_per_scene")),
            )

    with rollouts:
        with st.container(border=True):
            st.markdown("##### Factual Rollout Evidence")
            st.caption(
                "Selected rollout traces and their finite-candidate support, separate from source and target coverage."
            )
            first, second = st.columns(2)
            first.metric("Factual Rollout Traces", _header_metric_value(summary.get("rollouts")))
            second.metric("Factual Steps", _header_metric_value(summary.get("steps")))
            st.metric("Candidate Rows", _header_metric_value(summary.get("candidates")))
            st.metric(
                "Rollouts / Actor-Valid Target",
                _header_ratio_value(
                    _header_ratio(summary.get("rollouts"), summary.get("actor_valid_targets_with_rollouts"))
                ),
            )
            st.metric("Candidates / Step", _header_ratio_value(summary.get("candidates_per_step")))
            rollout_value, rollout_delta = _split_metric(summary.get("rollout_split_counts"))
            st.metric("Rollout Split (Train/Val/Test)", rollout_value, delta=rollout_delta, delta_color="off")

    coverage, footprint = st.columns(2)
    with coverage:
        with st.container(border=True):
            st.markdown("##### Reference Dataset Coverage")
            st.caption("Source footprint against the full 100-scene, 4,608-window GT-mesh ASE target.")
            first, second = st.columns(2)
            first.metric(
                "GT-Mesh Scene Coverage",
                _header_coverage_percentage(summary.get("source_scenes"), summary.get("reference_scene_count")),
            )
            second.metric(
                "GT-Mesh Snippet Coverage",
                _header_coverage_percentage(summary.get("source_snippets"), summary.get("reference_snippet_count")),
            )
            first, second = st.columns(2)
            first.metric(
                "Unrepresented GT-Mesh Scenes",
                _coverage_gap(summary.get("source_scenes"), summary.get("reference_scene_count")),
            )
            second.metric(
                "Unrepresented GT-Mesh Snippets",
                _coverage_gap(summary.get("source_snippets"), summary.get("reference_snippet_count")),
            )

    with footprint:
        with st.container(border=True):
            st.markdown("##### Physical Store Footprint")
            st.caption("On-disk Zarr payload and normalized storage cost; this is not the acquisition-cost metric.")
            first, second = st.columns(2)
            first.metric("Physical Store Footprint", _header_bytes_value(summary.get("store_bytes")))
            second.metric("Zarr Files", _header_metric_value(summary.get("store_files")))
            first, second = st.columns(2)
            first.metric("Bytes / Factual Rollout", _header_bytes_value(summary.get("bytes_per_rollout")))
            second.metric("Bytes / Factual Step", _header_bytes_value(summary.get("bytes_per_step")))
            st.metric("Bytes / Candidate", _header_bytes_value(summary.get("bytes_per_candidate")))

    st.caption(
        "Coverage follows the persisted target table and target-to-rollout linkage. Per-scene target counts cover represented "
        "scenes only; targets without a rollout trace remain visible in the coverage denominator but cannot be assigned a scene."
    )
    st.caption(
        "Header facts use manifest/root metadata plus compact target and rollout linkage; they do not load candidate or step "
        "audit projections."
    )


def _header_metric_value(value: object) -> str:
    """Format optional header facts without treating missing metadata as zero."""

    if value is None:
        return "Unavailable"
    return f"{int(value):,}" if isinstance(value, int) else str(value)


def _header_ratio_value(value: object) -> str:
    """Format one derived store-composition ratio or preserve its absence."""

    return f"{float(value):.2f}" if isinstance(value, float) else "Unavailable"


def _header_ratio(numerator: object, denominator: object) -> float | None:
    """Return one header ratio while preserving missing and zero-denominator facts."""

    if not isinstance(numerator, int) or not isinstance(denominator, int) or denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _header_coverage_value(numerator: object, denominator: object) -> str:
    """Format a compositional numerator/denominator header metric."""

    if not isinstance(numerator, int) or not isinstance(denominator, int):
        return "Unavailable"
    return f"{numerator:,} / {denominator:,}"


def _header_coverage_percentage(numerator: object, denominator: object) -> str:
    """Format reference coverage as a numerator, denominator, and percentage."""

    value = _header_coverage_value(numerator, denominator)
    ratio = _header_ratio(numerator, denominator)
    return value if ratio is None else f"{value} ({100.0 * ratio:.2f}%)"


def _coverage_gap(numerator: object, denominator: object) -> str:
    """Format the unrepresented part of one fixed reference population."""

    if not isinstance(numerator, int) or not isinstance(denominator, int):
        return "Unavailable"
    return f"{max(0, denominator - numerator):,}"


def _header_bytes_value(value: object) -> str:
    """Format a finite byte count with an explicit binary unit."""

    if not isinstance(value, (int, float)) or value < 0:
        return "Unavailable"
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024.0 or unit == "TiB":
            return f"{amount:.1f} {unit}"
        amount /= 1024.0
    return "Unavailable"


def _render_dataset_coverage_footprint(summary: dict[str, object]) -> None:
    """Render compact coverage composition and source-footprint plots."""

    st.markdown("#### Dataset Coverage & Footprint")
    st.caption(
        "Coverage is the source footprint relative to the 100-scene, 4,608-window GT-mesh reference. "
        "It measures scale, not target-label or QH-supervision coverage."
    )
    reference, scene_footprint = st.columns(2)
    with reference:
        _render_plot(_reference_coverage_figure(summary))
    with scene_footprint:
        figure = _source_footprint_figure(summary)
        if figure is None:
            st.info("No scene-resolved source footprint is available in this store manifest.")
        else:
            _render_plot(figure)


def _reference_coverage_figure(summary: dict[str, object]):
    """Build a compositional represented-versus-unrepresented coverage chart."""

    populations = (
        ("GT-Mesh Scenes", "source_scenes", "reference_scene_count"),
        ("GT-Mesh Snippet Windows", "source_snippets", "reference_snippet_count"),
    )
    rows: list[dict[str, object]] = []
    for population, observed_key, reference_key in populations:
        observed = summary.get(observed_key)
        reference = summary.get(reference_key)
        if not isinstance(observed, int) or not isinstance(reference, int):
            continue
        rows.extend(
            (
                {"population": population, "coverage": "Represented", "count": min(observed, reference)},
                {"population": population, "coverage": "Unrepresented", "count": max(0, reference - observed)},
            )
        )
    if not rows:
        figure = go.Figure()
        figure.add_annotation(text="Reference coverage is unavailable", showarrow=False)
        figure.update_layout(title="Reference Dataset Coverage", height=310)
        return figure
    figure = px.bar(
        pd.DataFrame(rows),
        y="population",
        x="count",
        color="coverage",
        orientation="h",
        text="count",
        barmode="stack",
        color_discrete_map={"Represented": "#14b8a6", "Unrepresented": "#475569"},
        labels={"population": "Reference Population", "count": "Count", "coverage": "Coverage"},
        title="Reference Dataset Coverage",
    )
    figure.update_layout(height=310)
    return figure


def _source_footprint_figure(summary: dict[str, object]):
    """Build a per-scene source row/window footprint chart when manifest detail exists."""

    footprint = summary.get("source_footprint_by_scene")
    if not isinstance(footprint, dict):
        return None
    rows: list[dict[str, object]] = []
    for scene, values in sorted(footprint.items()):
        if not isinstance(values, dict):
            continue
        for label, key in (("Source Rows", "source_rows"), ("Unique Snippet Windows", "source_snippets")):
            value = values.get(key)
            if isinstance(value, int):
                rows.append({"scene": str(scene), "measure": label, "count": value})
    if not rows:
        return None
    figure = px.bar(
        pd.DataFrame(rows),
        x="scene",
        y="count",
        color="measure",
        barmode="group",
        text="count",
        color_discrete_map={"Source Rows": "#38bdf8", "Unique Snippet Windows": "#a78bfa"},
        labels={"scene": "Scene", "count": "Source Footprint", "measure": "Population"},
        title="Source Footprint by Represented Scene",
    )
    figure.update_layout(height=310)
    return figure


def _header_distribution_value(value: object) -> str:
    """Format a min/median/max metadata distribution without coercing absence."""

    if not isinstance(value, tuple) or len(value) != 3:
        return "Unavailable"
    minimum, median, maximum = value
    return f"{minimum} / {median:.2f} / {maximum}"


def _q_h_return_value(summary: dict[str, object]) -> str:
    """Format the persisted Q_H return contract only when it is complete."""

    semantics = summary.get("q_h_return_semantics")
    gamma = summary.get("discount_gamma")
    if not isinstance(semantics, str) or not isinstance(gamma, float):
        return "Unavailable"
    return f"{semantics} · γ={gamma:.2f}"


def _split_metric(value: object) -> tuple[str, str]:
    """Format train/val/test fractions and counts from one persisted population."""

    if not isinstance(value, dict):
        return "Unavailable", ""
    counts = {split: int(value.get(split, 0)) for split in ("train", "val", "test")}
    total = sum(counts.values())
    fractions = [float(counts[split]) / float(total) if total else 0.0 for split in counts]
    return (
        " / ".join(f"{fraction:.2f}" for fraction in fractions),
        " / ".join(f"{counts[split]:,}" for split in counts) + " rows",
    )


def _render_trust_and_topology(
    *,
    session: StoredRolloutSession,
    paths: PathConfig,
) -> None:
    st.subheader("Trust & Topology")
    _info_popover("Store evidence and provenance", _OVERVIEW_INFO)

    try:
        invariants = session.invariants()
    except Exception as exc:
        invariants = [{"status": "FAIL", "invariant": "invariant projection", "evidence": str(exc)}]
    inv_df = pd.DataFrame(invariants)
    st.markdown("#### Invariant matrix")
    st.caption(
        "PASS is established evidence; WARN is incomplete comparability; FAIL blocks scientific and Rerun claims."
    )
    st.dataframe(inv_df, hide_index=True, width="stretch")
    _download_frame("Download invariant CSV", "rollout-invariants.csv", inv_df)
    _download_json("Download invariant JSON", "rollout-invariants.json", invariants)

    _render_dataset_coverage_footprint(session.header_summary)

    vin_dirs = discover_vin_store_dirs(paths.offline_cache_dir)
    try:
        topology = session.topology(
            vin_store_dirs=tuple(path.as_posix() for path in vin_dirs),
            paths=paths,
        )
    except Exception as exc:
        st.warning(f"Topology could not be fully resolved: {type(exc).__name__}: {exc}")
        topology = None
    if topology is not None:
        st.markdown("#### Semantic lineage")
        sankey = topology.sankey_data()
        if sankey.get("link", {}).get("source"):
            fig = go.Figure(go.Sankey(node=sankey["node"], link=sankey["link"]))
            fig.update_layout(title="Persisted payloads and cross-store pointers", height=480)
            _render_plot(fig)
        modality_df = pd.DataFrame(topology.modality_rows())
        if not modality_df.empty:
            st.dataframe(modality_df, hide_index=True, width="stretch")
            _download_frame("Download modality matrix CSV", "dataset-modalities.csv", modality_df)
        with st.expander("Selected-source drill-down and plain-text tree"):
            source_rows = topology.source_rows()
            if source_rows:
                source_id = st.selectbox(
                    "Source row",
                    options=[int(row["source_row_id"]) for row in source_rows],
                    format_func=lambda value: next(
                        (
                            f"{value} · {row.get('scene_id', '?')} / {row.get('snippet_id', '?')}"
                            for row in source_rows
                            if int(row["source_row_id"]) == value
                        ),
                        str(value),
                    ),
                    key="stored_topology_source_row",
                )
                topology = session.topology(
                    vin_store_dirs=tuple(path.as_posix() for path in vin_dirs),
                    paths=paths,
                    selected_source_row_id=int(source_id),
                )
                st.dataframe(
                    [row for row in source_rows if int(row["source_row_id"]) == int(source_id)],
                    hide_index=True,
                    width="stretch",
                )
            st.code(topology.plain_text_tree(), language="text")
        _download_json("Download topology JSON", "dataset-topology.json", topology.to_jsonable())

        st.markdown("#### Physical Zarr layout")
        st.caption(
            "This view opens group and array metadata only. Shapes, dtypes, chunks, containment, and "
            "schema-declared references remain separated by physical store; array payloads are not sliced."
        )
        vin_roots = sorted(
            {
                Path(str(node["path"])).expanduser().resolve()
                for node in topology.node_rows()
                if node.get("kind") == "VIN manifest" and node.get("availability") != "absent" and node.get("path")
            },
            key=lambda path: path.as_posix(),
        )
        if not vin_roots:
            st.info("No uniquely resolved VIN root is available for physical metadata inspection.")
        for vin_root in vin_roots:
            try:
                layout = build_native_dataset_layout(
                    root_store_dir=vin_root,
                    rollout_store_dirs=(session.store_path,),
                )
            except Exception as exc:
                st.warning(f"Physical topology for `{vin_root}` is unavailable: {type(exc).__name__}: {exc}")
                continue
            if len(vin_roots) > 1:
                st.markdown(f"**VIN root:** `{vin_root}`")
            render_topology_snapshot(
                node_rows=[
                    {
                        "path": node.path,
                        "kind": node.kind,
                        "role": node.role,
                        **node.details,
                    }
                    for node in layout.nodes
                ],
                edge_rows=[
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "relation": edge.relation,
                        "status": edge.status,
                        "evidence": edge.evidence,
                    }
                    for edge in layout.edges
                ],
                tree_text=layout.tree_text(),
                diagram_dot=layout.graphviz_dot(),
            )

    with st.expander("Raw store metadata"):
        st.json({"inventory": session.inventory_row, **session.manifest_payload}, expanded=False)
    _download_json(
        "Download store metadata JSON",
        "rollout-store-metadata.json",
        {"inventory": session.inventory_row, **session.manifest_payload},
    )


def render(
    *,
    session: StoredRolloutSession,
    paths: PathConfig,
) -> None:
    """Render store trust evidence and cross-store topology."""

    _render_trust_and_topology(
        session=session,
        paths=paths,
    )


__all__ = [
    "_render_header_metrics",
    "_render_role_legend",
    "_render_store_selector",
    "render",
]
