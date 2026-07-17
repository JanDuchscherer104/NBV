"""Typed shared context for VIN diagnostics tab renderers.

The container provides one coherent session state, model output, oracle batch,
experiment configuration, and capability flags so every tab renders the same
forward pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....data_handling import VinOracleBatch
    from ....lightning.aria_nbv_experiment import AriaNBVExperimentConfig
    from ....vin.types import VinPrediction
    from ....vin.types.diagnostics import VinForwardDiagnostics
    from ...state_types import VinDiagnosticsState


@dataclass(slots=True)
class VinDiagContext:
    """Bind all tab renderers to one cached VIN forward pass."""

    state: "VinDiagnosticsState"
    """Session owner of runtime objects, outputs, tracebacks, and summaries."""

    debug: "VinForwardDiagnostics"
    """Model-internal actor-evidence tensors from the selected forward pass."""

    pred: "VinPrediction"
    """Actor-facing VIN scores, including ``Tensor[\"B N\", float32]`` expectations."""

    batch: "VinOracleBatch"
    """Input batch; RRI targets, GT OBBs, and attached meshes remain oracle-only."""

    cfg: "AriaNBVExperimentConfig"
    """Resolved experiment configuration used to create the runtime and batch."""

    use_offline_cache: bool
    """Whether input tensors came from the immutable VIN offline store."""

    attach_snippet: bool
    """Whether the configured source should retain snippet geometry for plots."""

    include_gt_mesh: bool
    """Whether full snippets may carry a GT mesh for explicit evaluation overlays."""

    has_tokens: bool
    """Whether VIN v1 frustum-token tensors are present in :attr:`debug`."""

    has_semidense_frustum: bool
    """Whether semidense projection diagnostics are present for this VIN variant."""

    num_candidates: int
    """Candidate width ``N`` shared by batch, prediction, and debug tensors."""


__all__ = ["VinDiagContext"]
