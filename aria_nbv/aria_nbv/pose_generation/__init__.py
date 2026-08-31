"""Finite-candidate generation contracts.

The canonical deep operation is
``CandidateGenerator.generate(CandidateRequest) -> CandidateSet``. The set
retains one full attempted table, typed admission evidence, ordered hard-valid
rows, action rows, completion, randomness revision, and semantic provenance.

Target-conditioned candidate generation adds a runtime-only actor-visible
target context. `TARGET_POINT` candidates must use the selected
observed/predicted target center, not GT geometry. Counterfactual transitions
and oracle rollout scorers live in `aria_nbv.rollouts`.

``CandidateViewGenerator``, ``CandidateMixtureViewGenerator``, their configs,
``CandidateGenerationRuntimeContext``, and ``CandidateSamplingResult`` remain
compatibility-only authoring/projection surfaces during the staged migration.
"""

from .candidate_generation import CandidateViewGenerator, CandidateViewGeneratorConfig
from .candidate_interface import (
    ActorTargetContext,
    AdmissionEvidence,
    CandidateConditioning,
    CandidateGenerator,
    CandidateRequest,
    CandidateSet,
    CandidateTable,
    PreparedCandidateScene,
    candidate_set_to_legacy_result,
)
from .candidate_mixture import (
    CandidateMixtureComponentConfig,
    CandidateMixtureViewGenerator,
    CandidateMixtureViewGeneratorConfig,
    candidate_position_id,
    candidate_strategy_id,
)
from .candidate_program import CandidateProgram, compile_candidate_program
from .program_generator import ProgramCandidateGenerator
from .sampling_keys import CandidateSamplingKey, CandidateSubstreamRevision
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
    "ActorTargetContext",
    "AdmissionEvidence",
    "CandidateConditioning",
    "CandidateGenerator",
    "CandidateProgram",
    "CandidateRequest",
    "CandidateSamplingKey",
    "CandidateSet",
    "CandidateSubstreamRevision",
    "CandidateTable",
    "CandidateViewGenerator",
    "CandidateViewGeneratorConfig",
    "PreparedCandidateScene",
    "ProgramCandidateGenerator",
    "CandidateMixtureComponentConfig",
    "CandidateMixtureViewGenerator",
    "CandidateMixtureViewGeneratorConfig",
    "CandidateGenerationRuntimeContext",
    "CandidatePositionMode",
    "ViewDirectionMode",
    "candidate_position_id",
    "candidate_set_to_legacy_result",
    "candidate_strategy_id",
    "compile_candidate_program",
    "CandidateSamplingResult",
    "SamplingStrategy",
    "CollisionBackend",
    "summarise_offsets_ref",
    "summarise_dirs_ref",
    "stats_to_markdown_table",
]
