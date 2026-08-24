"""Strongly typed Streamlit session state for the refactored app.

This module wraps Streamlit's `st.session_state` and therefore depends on
Streamlit. For Streamlit-free state types and cache key helpers, see
`aria_nbv.app.state_types`.
"""

from __future__ import annotations

from typing import Any, cast

import streamlit as st

from ..data_handling import AseEfmDatasetConfig
from ..oracle.pipelines.scene_labels import OracleRriLabelerConfig
from .scientific_labels import LABEL_DISPLAY_MODES, LabelDisplayMode
from .state_types import (
    AppState,
    CandidatesCache,
    DataCache,
    DepthCache,
    PointCloudCache,
    RriCache,
    VinDiagnosticsState,
    candidates_key,
    config_signature,
    depths_key,
    pcs_key,
    sample_key,
)

STATE_KEY = "nbv_app_state_v2"
"""Streamlit session key for the main :class:`AppState` graph."""

VIN_DIAG_STATE_KEY = "vin_diag_state_v1"
"""Streamlit session key for the independent VIN diagnostics cache."""

LABEL_DISPLAY_MODE_KEY = "nbv_label_display_mode_v1"
"""Session key for the app-wide scientific label display preference."""


def get_label_display_mode() -> LabelDisplayMode:
    """Return the validated app-wide scientific label display preference."""

    raw = st.session_state.get(LABEL_DISPLAY_MODE_KEY, "Both")
    if raw in LABEL_DISPLAY_MODES:
        return cast(LabelDisplayMode, raw)
    st.session_state[LABEL_DISPLAY_MODE_KEY] = "Both"
    return "Both"


def set_label_display_mode(mode: str) -> LabelDisplayMode:
    """Persist a valid scientific label display preference."""

    if mode not in LABEL_DISPLAY_MODES:
        raise ValueError(f"Unsupported label display mode: {mode!r}")
    selected = mode
    st.session_state[LABEL_DISPLAY_MODE_KEY] = selected
    return selected


def get_state(default_dataset: AseEfmDatasetConfig, default_labeler: OracleRriLabelerConfig) -> AppState:
    """Return the main session state, creating it from the supplied defaults.

    Existing state owns its mutable caches until :func:`clear_state` removes
    the session entry; later default arguments do not replace it.
    """

    raw = st.session_state.get(STATE_KEY)
    if isinstance(raw, AppState):
        return raw
    state = AppState(dataset_cfg=default_dataset, labeler_cfg=default_labeler, sample_idx=0)
    st.session_state[STATE_KEY] = state
    return state


def get_vin_state() -> VinDiagnosticsState:
    """Return the session VIN cache, migrating compatible legacy containers.

    Legacy mappings or objects are copied field-by-field into the current
    dataclass before the typed value replaces the old session entry.
    """

    raw = st.session_state.get(VIN_DIAG_STATE_KEY)
    if isinstance(raw, VinDiagnosticsState):
        return raw
    state = VinDiagnosticsState()
    if raw is not None:
        fields = VinDiagnosticsState.__dataclass_fields__.keys()
        if isinstance(raw, dict):
            for name in fields:
                if name in raw:
                    setattr(state, name, raw[name])
        else:
            for name in fields:
                if hasattr(raw, name):
                    setattr(state, name, getattr(raw, name))
    st.session_state[VIN_DIAG_STATE_KEY] = state
    return state


def store_state(state: AppState) -> None:
    """Store the mutable main-state graph under the canonical session key."""

    st.session_state[STATE_KEY] = state


def safe_rerun() -> None:
    """Request a Streamlit rerun through the current or legacy public API."""

    if hasattr(st, "rerun"):
        st.rerun()
        return
    experimental_rerun: Any = getattr(st, "experimental_rerun", None)
    if callable(experimental_rerun):
        experimental_rerun()
        return
    raise RuntimeError("Streamlit rerun API not available.")  # pragma: no cover


def clear_state() -> None:
    """Drop only the main NBV state; VIN diagnostics remain independently cached."""

    st.session_state.pop(STATE_KEY, None)


def get_cached_state() -> AppState:
    """Return the already-initialized main state or raise ``KeyError``."""

    return cast(AppState, st.session_state[STATE_KEY])


__all__ = [
    "AppState",
    "CandidatesCache",
    "DataCache",
    "DepthCache",
    "PointCloudCache",
    "RriCache",
    "STATE_KEY",
    "LABEL_DISPLAY_MODE_KEY",
    "candidates_key",
    "clear_state",
    "config_signature",
    "depths_key",
    "get_cached_state",
    "get_label_display_mode",
    "get_state",
    "pcs_key",
    "safe_rerun",
    "sample_key",
    "set_label_display_mode",
    "store_state",
]
