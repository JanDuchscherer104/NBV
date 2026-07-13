"""Strongly typed Streamlit session state for the refactored app.

This module wraps Streamlit's `st.session_state` and therefore depends on
Streamlit. For Streamlit-free state types and cache key helpers, see
`aria_nbv.app.state_types`.
"""

from __future__ import annotations

from typing import cast

import streamlit as st

from ..data_handling import AseEfmDatasetConfig
from ..oracle.pipelines.scene_labels import OracleRriLabelerConfig
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
VIN_DIAG_STATE_KEY = "vin_diag_state_v1"


def get_state(default_dataset: AseEfmDatasetConfig, default_labeler: OracleRriLabelerConfig) -> AppState:
    """Get or initialise the typed app state."""

    raw = st.session_state.get(STATE_KEY)
    if isinstance(raw, AppState):
        return raw
    state = AppState(dataset_cfg=default_dataset, labeler_cfg=default_labeler, sample_idx=0)
    st.session_state[STATE_KEY] = state
    return state


def get_vin_state() -> VinDiagnosticsState:
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
    st.session_state[STATE_KEY] = state


def safe_rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
        return
    if hasattr(st, "experimental_rerun"):
        st.experimental_rerun()  # type: ignore[attr-defined]
        return
    raise RuntimeError("Streamlit rerun API not available.")  # pragma: no cover


def clear_state() -> None:
    st.session_state.pop(STATE_KEY, None)


def get_cached_state() -> AppState:
    return cast(AppState, st.session_state[STATE_KEY])


__all__ = [
    "AppState",
    "CandidatesCache",
    "DataCache",
    "DepthCache",
    "PointCloudCache",
    "RriCache",
    "STATE_KEY",
    "candidates_key",
    "clear_state",
    "config_signature",
    "depths_key",
    "get_cached_state",
    "get_state",
    "pcs_key",
    "safe_rerun",
    "sample_key",
    "store_state",
]
