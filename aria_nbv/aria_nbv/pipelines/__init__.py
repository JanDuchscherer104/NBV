"""Reusable pipelines built on top of the oracle RRI components.

This package facade exports :class:`OracleRriLabeler`, its config factory, and
the labeled-sample DTO from :mod:`aria_nbv.pipelines.oracle_rri_labeler`. The
implementation module owns candidate-to-label orchestration; lower-level pose
generation, rendering, and RRI computation remain in their respective
packages.

The dashboard (Streamlit) is intentionally kept as a thin visualization layer.
Training and offline label generation should use the non-UI pipelines in this
package so data-flow, batching, and performance controls remain explicit.
"""

from .oracle_rri_labeler import OracleRriLabeler, OracleRriLabelerConfig, OracleRriSample

__all__ = [
    "OracleRriSample",
    "OracleRriLabeler",
    "OracleRriLabelerConfig",
]
