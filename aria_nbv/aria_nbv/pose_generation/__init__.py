"""Finite-candidate generation contracts.

The package owns the thesis action space: every NBV decision is a finite table
of candidate camera poses, validity masks, reason codes, and provenance fields.
`CandidateSamplingResult.views` is the compact valid table used for rendering
and scoring; `mask_valid`, `shell_poses`, strategy ids, mixture ids, and sampler
probabilities stay aligned to the full sampled shell so invalid actions remain
auditable instead of becoming low-RRI samples.

Target-conditioned candidate generation adds a runtime-only actor-visible
target context. `TARGET_POINT` candidates must use the selected
observed/predicted target center, not GT geometry. Counterfactual transitions
and oracle rollout scorers live in `aria_nbv.rollouts`.
"""

from .candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from .candidate_mixture import (
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGenerator,
    CandidateMixtureViewGeneratorConfig,
    candidate_position_id,
    candidate_strategy_id,
)
from .config import (
    BoxViewJitterConfig,
    CandidateGazeConfig,
    NoViewJitterConfig,
    SampledCenterConfig,
    SphericalViewJitterConfig,
    TargetOrbitCenterConfig,
)
from .types import (
    CandidateGenerationRuntimeContext,
    CandidatePositionMode,
    CandidateSamplingResult,
    CollisionBackend,
    SamplingStrategy,
    ViewDirectionMode,
)
from .utils import (
    stats_to_markdown_table,
    summarise_dirs_ref,
    summarise_offsets_ref,
)

__all__ = [
    "CandidateViewGenerator",
    "CandidateViewGeneratorConfig",
    "BoxViewJitterConfig",
    "CandidateGazeConfig",
    "CandidateMixtureComponentConfig",
    "CandidateMixtureViewGenerator",
    "CandidateMixtureViewGeneratorConfig",
    "CandidateGenerationRuntimeContext",
    "CandidatePositionMode",
    "NoViewJitterConfig",
    "SampledCenterConfig",
    "SphericalViewJitterConfig",
    "TargetOrbitCenterConfig",
    "ViewDirectionMode",
    "candidate_position_id",
    "candidate_strategy_id",
    "CandidateSamplingResult",
    "SamplingStrategy",
    "CollisionBackend",
    "summarise_offsets_ref",
    "summarise_dirs_ref",
    "stats_to_markdown_table",
]
