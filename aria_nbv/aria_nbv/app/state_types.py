"""Streamlit-free state types and cache keys for the refactored app.

This module intentionally contains **no Streamlit imports** so it can be reused in
non-UI contexts (training/CLI) that still want the same caching semantics.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import torch

from ..data_handling import AseEfmDatasetConfig, EfmSnippetView, VinOracleBatch
from ..lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ..pipelines import OracleRriLabelerConfig
from ..pose_generation.types import CandidateSamplingResult
from ..rendering.candidate_depth_renderer import CandidateDepths
from ..rendering.candidate_pointclouds import CandidatePointClouds
from ..rri_metrics.types import RriResult
from ..vin.types import VinForwardDiagnostics, VinPrediction


def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, (Path, torch.device, torch.dtype)):
        return str(value)

    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()

    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]

    if is_dataclass(value):
        return _to_jsonable(asdict(value))

    if hasattr(value, "model_dump"):
        return _to_jsonable(value.model_dump(mode="python", round_trip=True))

    return str(value)


def config_signature(cfg: Any) -> str:
    """Return a stable JSON signature for a pydantic config object."""
    if hasattr(cfg, "model_dump"):
        payload = cfg.model_dump(mode="python", round_trip=True)  # type: ignore[call-arg]
    else:
        payload = dict(cfg)
    return json.dumps(_to_jsonable(payload), sort_keys=True)


@dataclass(slots=True)
class DataCache:
    cfg_sig: str | None = None
    sample_idx: int | None = None
    dataset_iter: Iterator[EfmSnippetView] | None = None
    last_iter_idx: int | None = None
    sample: EfmSnippetView | None = None


@dataclass(slots=True)
class CandidatesCache:
    cfg_sig: str | None = None
    sample_key: str | None = None
    candidates: CandidateSamplingResult | None = None


@dataclass(slots=True)
class DepthCache:
    cfg_sig: str | None = None
    sample_key: str | None = None
    candidates_key: str | None = None
    depths: CandidateDepths | None = None


@dataclass(slots=True)
class PointCloudCache:
    depth_key: str | None = None
    by_stride: dict[int, CandidatePointClouds] | None = None


@dataclass(slots=True)
class RriCache:
    cfg_sig: str | None = None
    pcs_key: str | None = None
    result: RriResult | None = None


@dataclass(slots=True)
class VinDiagnosticsState:
    """Session-scoped cache for VIN diagnostics."""

    cfg_sig: str | None = None
    experiment: AriaNBVExperimentConfig | None = None
    module: Any | None = None
    datamodule: Any | None = None
    batch: VinOracleBatch | None = None
    pred: VinPrediction | None = None
    debug: VinForwardDiagnostics | None = None
    error: str | None = None
    summary_key: str | None = None
    summary_text: str | None = None
    summary_error: str | None = None


@dataclass(slots=True)
class AppState:
    """All persistent app state (Streamlit-serialisable container)."""

    dataset_cfg: AseEfmDatasetConfig
    labeler_cfg: OracleRriLabelerConfig
    sample_idx: int = 0

    data: DataCache = field(default_factory=DataCache)
    candidates: CandidatesCache = field(default_factory=CandidatesCache)
    depth: DepthCache = field(default_factory=DepthCache)
    pcs: PointCloudCache = field(default_factory=PointCloudCache)
    rri: RriCache = field(default_factory=RriCache)


def sample_key(sample: EfmSnippetView) -> str:
    return f"{sample.scene_id}:{sample.snippet_id}"


def candidates_key(candidates: CandidateSamplingResult) -> str:
    """Return an in-session identity key for the current candidate set."""
    n = int(candidates.views.tensor().shape[0])
    ref = candidates.reference_pose.tensor().detach().cpu().numpy().tobytes()
    return f"n={n}:ref={hash(ref)}"


def depths_key(depths: CandidateDepths) -> str:
    """Return an in-session identity key for the rendered depth subset."""
    idx = tuple(int(i) for i in depths.candidate_indices.detach().cpu().tolist())
    return f"n={len(idx)}:idx={hash(idx)}"


def pcs_key(pcs: CandidatePointClouds) -> str:
    """Return an in-session identity key for backprojected candidate point clouds."""
    lengths = pcs.lengths.detach().cpu().tolist()
    return f"C={int(pcs.points.shape[0])}:P={int(pcs.points.shape[1])}:len={hash(tuple(int(x) for x in lengths))}"


__all__ = [
    "AppState",
    "CandidatesCache",
    "DataCache",
    "DepthCache",
    "PointCloudCache",
    "RriCache",
    "candidates_key",
    "config_signature",
    "depths_key",
    "pcs_key",
    "sample_key",
]
