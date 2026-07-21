"""Small learning contracts for scene-bundle RRI experiments."""

from .bundle import ActorSceneBundle, SceneBundleSupervision
from .factorized_rri import FactorizedRriModel, FactorizedRriTransformer, hierarchical_masked_loss
from .grouped_rollouts import ActorTargetQuery, GroupedRolloutTrainingBatch, grouped_rollout_training_batches

__all__ = [
    "ActorSceneBundle",
    "ActorTargetQuery",
    "FactorizedRriModel",
    "FactorizedRriTransformer",
    "GroupedRolloutTrainingBatch",
    "SceneBundleSupervision",
    "grouped_rollout_training_batches",
    "hierarchical_masked_loss",
]

