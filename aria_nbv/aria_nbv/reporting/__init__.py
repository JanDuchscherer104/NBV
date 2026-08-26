"""Immutable scientific reports shared by Streamlit, CLI, and Typst.

The public interface is intentionally small: validate a
``ScientificReportConfig``, construct its ``ScientificReportBuilder``, build a
``ReportSnapshot`` once, and pass that exact snapshot to
``write_report_snapshot``. Domain calculations remain in their rollout and W&B
owners; the reporting module owns freezing, notation validation, canonical
Plotly specifications, and publication.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .builder import ReportRequest, ScientificReportBuilder
    from .config import ScientificReportConfig
    from .errors import ScientificReportError
    from .export import ReportWriteReceipt, write_report_snapshot
    from .results import NamedQuantity, ReportColumn, ReportFigure, ReportSnapshot, ReportTable, SourceIdentity

_OWNERS = {
    "NamedQuantity": ".results",
    "ReportColumn": ".results",
    "ReportFigure": ".results",
    "ReportRequest": ".builder",
    "ReportSnapshot": ".results",
    "ReportTable": ".results",
    "ReportWriteReceipt": ".export",
    "ScientificReportBuilder": ".builder",
    "ScientificReportConfig": ".config",
    "ScientificReportError": ".errors",
    "SourceIdentity": ".results",
    "write_report_snapshot": ".export",
}


def __getattr__(name: str) -> Any:
    """Load one public report contract from its owning leaf module."""

    try:
        module_name = _OWNERS[name]
    except KeyError as error:
        raise AttributeError(name) from error
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value


__all__ = [
    "NamedQuantity",
    "ReportColumn",
    "ReportFigure",
    "ReportRequest",
    "ReportSnapshot",
    "ReportTable",
    "ReportWriteReceipt",
    "ScientificReportBuilder",
    "ScientificReportConfig",
    "ScientificReportError",
    "SourceIdentity",
    "write_report_snapshot",
]
