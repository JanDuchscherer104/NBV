"""Stable failure categories for scientific report construction and export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReportErrorCode = Literal[
    "config_invalid",
    "source_unavailable",
    "source_identity_changed",
    "result_invalid",
    "result_missing",
    "notation_unknown",
    "publication_gate_failed",
    "render_failed",
    "export_failed",
]


@dataclass(eq=False)
class ScientificReportError(RuntimeError):
    """Contextual failure crossing the reporting interface.

    Attributes:
        code: Stable machine-readable category.
        message: Human-readable failure detail.
        result_id: Optional result whose construction or export failed.
        source_id: Optional source whose acquisition or identity check failed.
    """

    code: ReportErrorCode
    """Stable machine-readable failure category."""

    message: str
    """Human-readable failure detail."""

    result_id: str | None = None
    """Result identifier implicated by the failure, when applicable."""

    source_id: str | None = None
    """Source identifier implicated by the failure, when applicable."""

    def __str__(self) -> str:
        context = [f"code={self.code}"]
        if self.source_id is not None:
            context.append(f"source={self.source_id}")
        if self.result_id is not None:
            context.append(f"result={self.result_id}")
        return f"{self.message} ({', '.join(context)})"


__all__ = ["ReportErrorCode", "ScientificReportError"]
