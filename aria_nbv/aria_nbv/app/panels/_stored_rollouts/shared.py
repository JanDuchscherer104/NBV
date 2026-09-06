"""Stored-rollout-specific presentation boundaries."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..common import EvidenceRole, download_json


def render_stale_store_boundary(
    validation: Any,
    *,
    inventory_row: dict[str, Any] | None,
    manifest_payload: dict[str, Any],
) -> None:
    """Explain why an invalid store is visible but cannot contribute evidence."""

    st.warning(
        "Scientific evidence and Rerun are disabled because this store does not pass the current schema contract."
    )
    for error in getattr(validation, "errors", ()):
        st.error(str(error))
    download_json(
        "Download stale-store diagnostics JSON",
        "stale-rollout-store.json",
        {"inventory": inventory_row, **manifest_payload, "validation_errors": list(getattr(validation, "errors", ()))},
    )


__all__ = ["EvidenceRole", "render_stale_store_boundary"]
