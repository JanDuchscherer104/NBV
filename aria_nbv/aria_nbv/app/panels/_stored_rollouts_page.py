"""Thin coordinator for the stored-rollout Streamlit inspector.

The current four-tab workflow remains public.  Its private presentation concerns
live in :mod:`aria_nbv.app.panels._stored_rollouts`; rollout semantics stay in
the typed inspection and reporting owners.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...configs import PathConfig
from ._stored_rollouts import failure_triage, inspect_rerun, session, validity_support
from ._stored_rollouts import overview_topology as overview
from ._stored_rollouts import reconstruction_return as reconstruction
from ._stored_rollouts.shared import (
    STORED_ROLLOUTS_DIAGNOSE_MODE_KEY,
    STORED_ROLLOUTS_DIAGNOSE_MODES,
    STORED_ROLLOUTS_SECTION_KEY,
    download_json,
    render_stale_store_boundary,
)

_SECTIONS = ("Overview", "Reward & reconstruction", "Admission & feasibility", "Diagnose a store")


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
        default=st.session_state.get(STORED_ROLLOUTS_SECTION_KEY, _SECTIONS[0]),
        key=STORED_ROLLOUTS_SECTION_KEY,
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
            reconstruction._render_corpus_temporal_evidence(corpus_summary)
            overview._render_corpus_endpoint_distributions(corpus_summary)
    if tabs[2].open:
        with tabs[2]:
            overview._render_corpus_admission(corpus_summary)
            if current:
                validity_support._render_targets_and_support(reader)
            else:
                render_stale_store_boundary(
                    validation, inventory_row=selected_inventory, manifest_payload=manifest_payload
                )
    if tabs[3].open:
        with tabs[3]:
            if not current:
                render_stale_store_boundary(
                    validation, inventory_row=selected_inventory, manifest_payload=manifest_payload
                )
            else:
                mode = st.radio(
                    "Diagnose mode",
                    options=STORED_ROLLOUTS_DIAGNOSE_MODES,
                    key=STORED_ROLLOUTS_DIAGNOSE_MODE_KEY,
                    horizontal=True,
                )
                if mode == STORED_ROLLOUTS_DIAGNOSE_MODES[0]:
                    overview._render_corpus_failures(corpus_summary)
                    failure_triage._render_failure_triage(reader)
                else:
                    overview._render_corpus_details(corpus_summary)
                    reconstruction._render_scientific_evidence(reader)
                    inspect_rerun._render_inspect_export_rerun(
                        reader, store_path=store_path, manifest_payload=manifest_payload, paths=paths
                    )


__all__ = ["render_stored_rollouts_page"]
