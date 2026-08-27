"""Private compact representations for data-handling view dataclasses.

The mixin and helpers in this module own formatting only. They deliberately do
not define transfer, collation, serialization, indexing, persistence, or
lifecycle behavior for the DTOs that reuse them.
"""

from __future__ import annotations

from dataclasses import fields
from pprint import pformat
from typing import Any, ClassVar

from ..configs.field_docs import inherited_field_docstring
from ..utils import summarize


def _compact_dataclass_repr(obj: Any, *, include_docstrings: bool) -> str:
    """Format summarized dataclass fields, optionally with field documentation."""

    items: dict[str, Any] = {}
    cls = obj.__class__
    for field in fields(obj):
        value = summarize(getattr(obj, field.name))
        if include_docstrings:
            doc = field.metadata.get("doc") if field.metadata else None
            if doc is None:
                doc = inherited_field_docstring(cls, field.name)
            items[field.name] = {"value": value, "doc": doc} if doc else {"value": value}
        else:
            items[field.name] = value
    return pformat(items, indent=2, width=100, compact=False)


class _CompactReprMixin:
    """Add compact dataclass formatting without any broader view contract."""

    __repr_docstrings__: ClassVar[bool] = False
    """Whether the default compact representation includes field documentation."""

    def __repr__(self) -> str:  # pragma: no cover - formatting only
        """Return summarized dataclass fields in the established compact format."""

        return _compact_dataclass_repr(self, include_docstrings=self.__repr_docstrings__)

    def repr_with_docstrings(self) -> str:  # pragma: no cover - formatting only
        """Return compact fields together with their inline documentation."""

        return _compact_dataclass_repr(self, include_docstrings=True)


__all__: list[str] = []
