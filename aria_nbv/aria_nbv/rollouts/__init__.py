"""Target-conditioned replay transitions and persisted rollout stores.

`aria_nbv.rollouts` owns the multi-step thesis replay and persistence surface.
Operational rollout-dataset generation lives in `aria_nbv.oracle.pipelines`;
raw snippet access and immutable VIN offline stores remain in
`aria_nbv.data_handling`.

The stable root exports replay and store entrypoints. Import validated
finite-horizon chain reading from :mod:`aria_nbv.rollouts.qh_reader` and pose
composition from :mod:`aria_nbv.rollouts.qh_geometry`.
"""

from .replay.engine import (
    CounterfactualPoseGenerator,
    CounterfactualPoseGeneratorConfig,
)
from .replay.policy import RolloutPolicySpec
from .replay.state import (
    CounterfactualRolloutResult,
    CounterfactualTrajectory,
)
from .replay.types import CandidateScores
from .zarr_store import (
    RolloutZarrStoreConfig,
    RolloutZarrStoreReader,
)

__all__ = [
    "CandidateScores",
    "CounterfactualPoseGenerator",
    "CounterfactualPoseGeneratorConfig",
    "CounterfactualRolloutResult",
    "CounterfactualTrajectory",
    "RolloutPolicySpec",
    "RolloutZarrStoreConfig",
    "RolloutZarrStoreReader",
]
