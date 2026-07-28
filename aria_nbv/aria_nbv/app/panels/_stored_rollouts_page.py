"""Thin coordinator for the modular persisted-rollout inspector."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...configs import PathConfig
from ._stored_rollouts import (
    candidate_generation,
    inspect_rerun,
    oracle_headroom,
    qh_admission,
    reconstruction_return,
    validity_support,
)
from ._stored_rollouts.overview_topology import (
    _render_header_metrics,
    _render_role_legend,
    _render_store_selector,
)
from ._stored_rollouts.overview_topology import (
    render as render_overview_topology,
)
from ._stored_rollouts.session import (
    StoredRolloutSession,
    open_stored_rollout_session,
    rollout_store_inventory,
)
from ._stored_rollouts.shared import (
    _SECTION_KEY,
    _download_json,
    _render_stale_store_boundary,
)

_SECTIONS = (
    "Overview & Topology",
    "Reconstruction & Return",
    "Oracle Headroom & Policies",
    "Validity & Support",
    "Candidate Generation & Selection",
    "QH Training Admission",
    "Inspect & Rerun",
)
_LEGACY_SECTIONS = {
    "Trust & Topology": "Overview & Topology",
    "Scientific Evidence": "Reconstruction & Return",
    "Targets & Action Support": "Validity & Support",
    "Failure Triage": "Validity & Support",
    "Inspect, Export & Rerun": "Inspect & Rerun",
}


def render_stored_rollouts_page() -> None:
    """Render the selected rollout-supervision section only."""

    st.header("Rollout Supervision")
    st.caption(
        "Inspect persisted rollout Zarr artifacts: trust the artifact first, compare only matched evidence, "
        "then inspect one failure or rollout in depth."
    )
    _render_role_legend()

    paths = PathConfig()
    inventory = rollout_store_inventory(paths.offline_cache_dir.as_posix())
    store_path = _render_store_selector(paths, inventory)
    if store_path is None:
        st.info("No rollout store is selected. Choose a discovered store or enter a path.")
        return

    selected_inventory = next((row for row in inventory if Path(str(row["path"])) == store_path), None)
    try:
        session = open_stored_rollout_session(store_path, inventory_row=selected_inventory)
    except Exception as exc:
        st.error(f"The selected store cannot be opened: {type(exc).__name__}: {exc}")
        _download_json("Download store identity JSON", "rollout-store-identity.json", selected_inventory or {})
        return

    _render_header_metrics(session.header_summary, validation_ok=bool(session.validation.ok))

    selected_section = _normalized_section(st.session_state.get(_SECTION_KEY))
    if st.session_state.get(_SECTION_KEY) != selected_section:
        st.session_state[_SECTION_KEY] = selected_section
    selected_section_value = st.segmented_control(
        "Rollout supervision section",
        list(_SECTIONS),
        selection_mode="single",
        required=True,
        key=_SECTION_KEY,
        label_visibility="collapsed",
        width="stretch",
    )
    _render_selected_section(
        _normalized_section(selected_section_value),
        session=session,
        paths=paths,
    )


def _normalized_section(value: object) -> str:
    """Map persisted legacy tab labels onto the current section vocabulary."""

    section = _LEGACY_SECTIONS.get(str(value), str(value))
    return section if section in _SECTIONS else _SECTIONS[0]


def _render_selected_section(
    section: str,
    *,
    session: StoredRolloutSession,
    paths: PathConfig,
) -> None:
    """Dispatch exactly one active section renderer."""

    if section == "Overview & Topology":
        render_overview_topology(
            session=session,
            paths=paths,
        )
        return
    if not bool(session.validation.ok):
        _render_stale_store_boundary(
            session.validation,
            inventory_row=session.inventory_row,
            manifest_payload=session.manifest_payload,
        )
        return

    if section == "Reconstruction & Return":
        reconstruction_return.render(session)
        return
    if section == "Oracle Headroom & Policies":
        oracle_headroom.render(session)
        return
    if section == "Validity & Support":
        validity_support.render(session)
        return
    if section == "Candidate Generation & Selection":
        candidate_generation.render(session)
        return
    if section == "QH Training Admission":
        qh_admission.render(session)
        return
    if section == "Inspect & Rerun":
        inspect_rerun.render(session, paths=paths)
        return
    raise ValueError(f"Unknown rollout-supervision section: {section!r}")


__all__ = ["render_stored_rollouts_page"]
