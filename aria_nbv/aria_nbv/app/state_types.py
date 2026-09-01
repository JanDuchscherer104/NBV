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
from typing import TYPE_CHECKING, Any

import torch

from ..data_handling import AseEfmDatasetConfig, EfmSnippetView, VinOracleBatch
from ..lightning.aria_nbv_experiment import AriaNBVExperimentConfig
from ..oracle.pipelines.scene_labels import OracleRriLabelerConfig
from ..pose_generation.types import CandidateSamplingResult
from ..rendering.candidate_depth_renderer import CandidateDepths
from ..rendering.candidate_pointclouds import CandidatePointClouds
from ..rri_metrics.rri import RriResult
from ..vin.types import VinPrediction
from ..vin.types.diagnostics import VinForwardDiagnostics
from .candidate_evidence import CandidateEvidenceView, LiveCandidateEvidenceRequest

if TYPE_CHECKING:
    from ..pose_generation import CandidateSet


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
    """Return a deterministic JSON signature for one configuration value."""

    if hasattr(cfg, "model_dump"):
        payload = cfg.model_dump(mode="python", round_trip=True)  # type: ignore[call-arg]
    else:
        payload = dict(cfg)
    return json.dumps(_to_jsonable(payload), sort_keys=True)


@dataclass(slots=True)
class DataCache:
    """Session-owned dataset iterator and its most recently materialized sample."""

    cfg_sig: str | None = None
    """Signature of the dataset configuration that created this cache."""

    sample_idx: int | None = None
    """Zero-based source index of :attr:`sample`."""

    dataset_iter: Iterator[EfmSnippetView] | None = None
    """Forward-only iterator reused while selection advances under one config."""

    last_iter_idx: int | None = None
    """Last source index consumed from :attr:`dataset_iter`."""

    sample: EfmSnippetView | None = None
    """Selected snippet; observed evidence is actor-visible, attached mesh/GT is oracle-only."""


@dataclass(slots=True)
class CandidatesCache:
    """Session cache for the actor-action candidate shell of one snippet."""

    cfg_sig: str | None = None
    """Signature of the candidate-generator configuration."""

    sample_key: str | None = None
    """Scene/snippet identity that produced :attr:`candidates`."""

    candidates: CandidateSamplingResult | None = None
    """Candidate poses, validity masks, and provenance aligned to the finite shell ``N``."""

    evidence: CandidateEvidenceView | None = None
    """Canonical immutable evidence retained when a truthful ``CandidateSet`` is supplied."""

    evidence_request: LiveCandidateEvidenceRequest | None = None
    """Complete external-composition identity behind :attr:`evidence`."""

    evidence_candidate_set: CandidateSet | None = None
    """Exact immutable scientific output behind :attr:`evidence`; compared by object identity."""


@dataclass(slots=True)
class DepthCache:
    """Session cache for mesh-rendered candidate depths used only by oracle/evaluation."""

    cfg_sig: str | None = None
    """Signature of the depth-renderer configuration."""

    sample_key: str | None = None
    """Scene/snippet identity of the rendered mesh source."""

    candidates_key: str | None = None
    """In-session identity of the candidate set rendered into :attr:`depths`."""

    depths: CandidateDepths | None = None
    """Metric z-depth ``Tensor[\"C H W\", float]`` and masks; never actor-visible."""


@dataclass(slots=True)
class PointCloudCache:
    """Session cache for oracle depth backprojections at requested pixel strides."""

    depth_key: str | None = None
    """In-session identity of the depth batch backing every cached stride."""

    by_stride: dict[int, CandidatePointClouds] | None = None
    """Oracle world-point clouds ``Tensor[\"C P 3\", float]`` in metres by positive stride."""


@dataclass(slots=True)
class RriCache:
    """Session cache for oracle RRI labels derived from one point-cloud batch."""

    cfg_sig: str | None = None
    """Signature of the complete oracle-labeler configuration."""

    pcs_key: str | None = None
    """In-session identity of the point clouds scored into :attr:`result`."""

    result: RriResult | None = None
    """Oracle scores ``Tensor[\"C\", float]`` and mesh-distance diagnostics."""


@dataclass(slots=True)
class VinDiagnosticsState:
    """Session-scoped runtime, outputs, and rendered-summary cache for VIN diagnostics."""

    cfg_sig: str | None = None
    """Signature of the experiment configuration backing all runtime fields."""

    experiment: AriaNBVExperimentConfig | None = None
    """Resolved experiment configuration used for the cached forward pass."""

    module: Any | None = None
    """Checkpoint-backed Lightning module retained for diagnostics reruns."""

    datamodule: Any | None = None
    """Prepared data module retained with :attr:`module` for batch iteration."""

    batch: VinOracleBatch | None = None
    """Last VIN batch; observed evidence is actor-visible while RRI/GT fields are oracle-only."""

    pred: VinPrediction | None = None
    """Last actor-facing VIN scores, including ``Tensor[\"B N\", float32]`` expectations."""

    debug: VinForwardDiagnostics | None = None
    """Last model-internal actor-evidence tensors, owned for interactive plotting."""

    error: str | None = None
    """Full traceback from the latest failed setup or forward pass."""

    summary_key: str | None = None
    """Identity of the configuration, sample, and options behind the cached summary."""

    summary_text: str | None = None
    """Captured plain-text model summary for :attr:`summary_key`."""

    summary_error: str | None = None
    """Displayable error from the latest model-summary attempt."""


@dataclass(slots=True)
class AppState:
    """Mutable root of the main Streamlit session and its invalidation chain."""

    dataset_cfg: AseEfmDatasetConfig
    """Current observed-snippet input configuration."""

    labeler_cfg: OracleRriLabelerConfig
    """Current candidate generator plus oracle depth/RRI label configuration."""

    sample_idx: int = 0
    """Zero-based sample index selected in the current dataset stream."""

    data: DataCache = field(default_factory=DataCache)
    """Upstream dataset cache; replacing its sample invalidates every downstream cache."""

    candidates: CandidatesCache = field(default_factory=CandidatesCache)
    """Actor-action candidate cache invalidated when input data or generator changes."""

    depth: DepthCache = field(default_factory=DepthCache)
    """Oracle-only rendered-depth cache invalidated when candidates change."""

    pcs: PointCloudCache = field(default_factory=PointCloudCache)
    """Oracle-only depth-backprojection cache invalidated when rendered depths change."""

    rri: RriCache = field(default_factory=RriCache)
    """Terminal oracle-label cache invalidated when its point clouds change."""


def sample_key(sample: EfmSnippetView) -> str:
    """Return the scene/snippet identity used for session-local cache joins."""

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
