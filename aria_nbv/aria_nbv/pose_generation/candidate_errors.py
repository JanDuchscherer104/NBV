"""Typed failure modes of the finite candidate-generation interface."""


class CandidateGenerationError(RuntimeError):
    """Base error for failures crossing the candidate-generation interface."""


class InvalidCandidateProgramError(CandidateGenerationError, ValueError):
    """The resolved program is unknown, inconsistent, or outside hard limits."""


class CandidateRequestMismatchError(CandidateGenerationError, ValueError):
    """Request facts, identities, execution state, or scene sources disagree."""


class CandidateBackendFailureError(CandidateGenerationError):
    """A configured geometry or sampling backend could not complete."""


class CandidateNumericalDegeneracyError(CandidateGenerationError, ValueError):
    """Required candidate geometry is numerically undefined."""


class CandidateAlignmentCorruptionError(CandidateGenerationError, ValueError):
    """Candidate rows, evidence, or index projections are misaligned."""


__all__ = [
    "CandidateAlignmentCorruptionError",
    "CandidateBackendFailureError",
    "CandidateGenerationError",
    "CandidateNumericalDegeneracyError",
    "CandidateRequestMismatchError",
    "InvalidCandidateProgramError",
]
