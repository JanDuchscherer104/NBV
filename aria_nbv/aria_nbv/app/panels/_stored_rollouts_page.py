"""Thin coordinator for the stored-rollout Streamlit inspector.

The current four-tab workflow remains public.  Its private presentation concerns
live in :mod:`aria_nbv.app.panels._stored_rollouts`; rollout semantics stay in
the typed inspection and reporting owners.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...configs import PathConfig
from ._stored_rollouts import candidate_generation, failure_triage, inspect_rerun, session, shared, validity_support
from ._stored_rollouts import overview_topology as overview
from ._stored_rollouts import reconstruction_return as reconstruction
from ._stored_rollouts.shared import download_json, render_stale_store_boundary

# Private compatibility aliases keep existing focused callers stable while tests
# migrate to the owning module.  Production dispatch uses the modules above.
_render_store_selector = overview._render_store_selector
_render_corpus_overview = overview._render_corpus_overview
_render_corpus_details = overview._render_corpus_details
_render_validated_store_header = overview._render_validated_store_header
_cached_store_bundle = session._cached_store_bundle
_cached_store_bundle_cached = session._cached_store_bundle_cached
_cached_projection = session._cached_projection
_cached_corpus_summary = session._cached_corpus_summary
_cached_evidence_bundle = session._cached_evidence_bundle
_cached_failures = session._cached_failures
_cached_topology = session._cached_topology
_store_projection_identity = session._store_projection_identity
_clear_stored_rollout_caches = session._clear_stored_rollout_caches
_render_q_h_evidence = inspect_rerun._render_q_h_evidence
_activate_query_store = inspect_rerun._activate_query_store
_apply_query_state = inspect_rerun._apply_query_state
_clear_query_state = inspect_rerun._clear_query_state
_consume_pending_promotion = inspect_rerun._consume_pending_promotion
_evaluate_query_frame = inspect_rerun._evaluate_query_frame
_query_key = inspect_rerun._query_key
_query_namespace = inspect_rerun._query_namespace
_query_source_frame = inspect_rerun._query_source_frame
_candidate_flow_figure = candidate_generation._candidate_flow_figure
_selected_action_flow_figure = candidate_generation._selected_action_flow_figure
_selected_action_flow_rows = candidate_generation._selected_action_flow_rows
_render_branching_evidence = reconstruction._render_branching_evidence
_render_selected_rank_and_geometry = reconstruction._render_selected_rank_and_geometry
_TEMPORAL_METRIC_LABELS = reconstruction._TEMPORAL_METRIC_LABELS
_temporal_evidence_role = reconstruction._temporal_evidence_role
_temporal_summary_figure = reconstruction._temporal_summary_figure
_download_frame = shared.download_frame
_download_json = shared.download_json
_plot_control_key = shared.plot_control_key
_serialize_frame_csv = shared.serialize_frame_csv
_serialize_json = shared.serialize_json

_SECTIONS = ("Overview", "Evidence", "Failures", "Drill-down")
_SECTION_KEY = "stored_rollouts_section"


def render_stored_rollouts_page() -> None:
    """Render corpus summaries and one active-store inspection workflow."""

    st.header("Rollout Supervision")
    st.caption(
        "Inspect persisted rollout Zarr artifacts: trust the artifact first, compare only matched evidence, "
        "then inspect one failure or rollout in depth."
    )
    overview._render_role_legend()

    paths = PathConfig()
    inventory = session._cached_inventory(paths.offline_cache_dir.as_posix())
    corpus_paths, store_path = overview._render_store_selector(paths, inventory)
    if store_path is None:
        st.info("No rollout store is selected. Choose a discovered store or enter a path.")
        return

    selected_inventory = next((row for row in inventory if Path(str(row["path"])) == store_path), None)
    try:
        reader, validation, manifest_payload = session._cached_store_bundle(store_path.as_posix())
    except Exception as exc:
        st.error(f"The selected store cannot be opened: {type(exc).__name__}: {exc}")
        download_json("Download store identity JSON", "rollout-store-identity.json", selected_inventory or {})
        return

    tabs = st.tabs(
        list(_SECTIONS),
        default=st.session_state.get(_SECTION_KEY, _SECTIONS[0]),
        key=_SECTION_KEY,
        on_change="rerun",
        width="stretch",
    )
    current = bool(validation.ok)
    corpus_identity = tuple(session._store_projection_identity(path.as_posix()) for path in corpus_paths)
    corpus_key = (tuple(path.as_posix() for path in corpus_paths), corpus_identity)
    corpus_state = st.session_state.get(session.CORPUS_SUMMARY_STATE_KEY)
    corpus_summary = corpus_state[1] if corpus_state and corpus_state[0] == corpus_key else None

    if tabs[0].open:
        with tabs[0]:
            if st.button("Build corpus summary", type="primary", width="stretch"):
                corpus_summary = session._cached_corpus_summary(*corpus_key)
                st.session_state[session.CORPUS_SUMMARY_STATE_KEY] = (corpus_key, corpus_summary)
            overview._render_corpus_overview(corpus_summary, selected_count=len(corpus_paths))
            overview._render_trust_and_topology(
                reader=reader,
                store_path=store_path,
                inventory_row=selected_inventory,
                manifest_payload=manifest_payload,
                paths=paths,
                validation_ok=current,
            )
    if tabs[1].open:
        with tabs[1]:
            overview._render_corpus_evidence(corpus_summary)
            if current:
                with st.expander("Active-store scientific evidence"):
                    reconstruction._render_scientific_evidence(reader)
                with st.expander("Active-store targets and action support"):
                    validity_support._render_targets_and_support(reader)
            else:
                render_stale_store_boundary(
                    validation, inventory_row=selected_inventory, manifest_payload=manifest_payload
                )
    if tabs[2].open:
        with tabs[2]:
            overview._render_corpus_failures(corpus_summary)
            if current:
                failure_triage._render_failure_triage(reader)
            else:
                render_stale_store_boundary(
                    validation, inventory_row=selected_inventory, manifest_payload=manifest_payload
                )
    if tabs[3].open:
        with tabs[3]:
            overview._render_corpus_details(corpus_summary)
            if current:
                inspect_rerun._render_inspect_export_rerun(
                    reader, store_path=store_path, manifest_payload=manifest_payload, paths=paths
                )
            else:
                render_stale_store_boundary(
                    validation, inventory_row=selected_inventory, manifest_payload=manifest_payload
                )


__all__ = ["render_stored_rollouts_page"]
