"""Context container for VIN diagnostics tabs."""

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
    """Shared context for VIN diagnostic tab renderers.

    Attributes:
        state: Session-scoped diagnostics state.
        debug: VIN forward debug outputs.
        pred: VIN predictions.
        batch: Oracle batch used for diagnostics.
        cfg: Experiment configuration used for the run.
        use_offline_cache: Whether the batch originates from the VIN offline store.
        attach_snippet: Whether snippets are expected to be present for geometry plots.
        include_gt_mesh: Whether GT meshes are present when loading full snippets.
        has_tokens: Whether frustum tokens are available (VIN v1).
        has_semidense_frustum: Whether semidense frustum diagnostics are available (VIN v2).
        num_candidates: Number of candidate views in the batch.
    """

    state: "VinDiagnosticsState"
    debug: "VinForwardDiagnostics"
    pred: "VinPrediction"
    batch: "VinOracleBatch"
    cfg: "AriaNBVExperimentConfig"
    use_offline_cache: bool
    attach_snippet: bool
    include_gt_mesh: bool
    has_tokens: bool
    has_semidense_frustum: bool
    num_candidates: int


__all__ = ["VinDiagContext"]
