"""Shared typed contracts for persisted, physical, and runtime topologies."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, runtime_checkable

TopologyRole = Literal[
    "actor-visible",
    "oracle/evaluation",
    "derived training data",
    "provenance",
    "structure",
    "error",
]
"""Shared scientific or structural ownership vocabulary for topology nodes."""

TopologyStatus = Literal[
    "materialized",
    "referenced",
    "optional",
    "absent",
    "embedded",
    "resolved pointer",
    "lineage only",
    "inferred path",
    "resolved",
    "blocked",
    "missing",
    "ambiguous",
]
"""Shared availability and relationship-resolution vocabulary."""


@runtime_checkable
class TopologyNode(Protocol):
    """Presentation-neutral node emitted by every topology adapter."""

    @property
    def node_id(self) -> str:
        """Return the stable snapshot-local node identifier."""

    @property
    def label(self) -> str:
        """Return the compact human-readable label."""

    @property
    def kind(self) -> str:
        """Return the adapter-specific structural kind."""

    @property
    def role(self) -> TopologyRole:
        """Return the node's shared ownership role."""

    @property
    def status(self) -> TopologyStatus:
        """Return the node's shared availability status."""

    def to_row(self) -> Mapping[str, object]:
        """Return a deterministic presentation row."""


@runtime_checkable
class TopologyRelationship(Protocol):
    """Presentation-neutral relationship emitted by every topology adapter."""

    source: str
    target: str
    relation: str

    @property
    def status(self) -> TopologyStatus:
        """Return the relationship's shared resolution status."""

    @property
    def evidence(self) -> str | None:
        """Return optional compact evidence for the relationship."""

    def to_row(self) -> Mapping[str, object]:
        """Return a deterministic presentation row."""


@runtime_checkable
class TopologySnapshot(Protocol):
    """Renderer-facing snapshot shared by all topology adapters."""

    def node_rows(self) -> Sequence[Mapping[str, object]]:
        """Return deterministic node rows."""

    def edge_rows(self) -> Sequence[Mapping[str, object]]:
        """Return deterministic relationship rows."""

    def tree_text(self) -> str:
        """Return a compact plain-text hierarchy."""

    def diagram_dot(self) -> str | None:
        """Return an optional Graphviz projection."""


def assert_topology_snapshot(snapshot: TopologySnapshot) -> TopologySnapshot:
    """Return ``snapshot`` after a strict runtime protocol check.

    This helper gives adapters and tests one explicit boundary without adding a
    second aggregate model beside their compatibility snapshot classes.
    """

    if not isinstance(snapshot, TopologySnapshot):
        raise TypeError(f"Expected a TopologySnapshot, got {type(snapshot).__name__}.")
    return snapshot


__all__ = [
    "TopologyNode",
    "TopologyRelationship",
    "TopologyRole",
    "TopologySnapshot",
    "TopologyStatus",
    "assert_topology_snapshot",
]
