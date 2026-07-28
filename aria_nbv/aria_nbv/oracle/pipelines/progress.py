"""Framework-neutral progress events for local dataset generation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    """Describe one observable phase of a dataset generation run.

    Writers emit immutable snapshots so CLI and Streamlit callers can render
    progress without owning generation state or importing writer internals.
    """

    stage: str
    """Stable lifecycle label such as ``generating``, ``writing``, or ``validating``."""

    completed: int
    """Number of samples completed within the current generation run."""

    total: int | None
    """Expected sample count, or ``None`` when the input stream has no known length."""

    message: str
    """Short human-readable description of the current operation."""


ProgressCallback: TypeAlias = Callable[[GenerationProgress], None]
"""Consumer invoked synchronously for each generation progress snapshot."""


__all__ = ["GenerationProgress", "ProgressCallback"]
