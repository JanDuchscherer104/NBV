"""Presentation-neutral topology for nested runtime data-transfer objects."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, ClassVar, Literal, Protocol, TypeGuard

from .contracts import TopologyRole, TopologyStatus

RuntimeTopologyRole = TopologyRole
"""Scientific role of a runtime DTO field."""


class _DataclassInstance(Protocol):
    """Runtime dataclass instance accepted by :func:`dataclasses.fields`."""

    __dataclass_fields__: ClassVar[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class RuntimeTopologyNode:
    """One object or field in a nested runtime DTO."""

    path: str
    """Stable dotted path rooted at the inspected object."""

    python_type: str
    """Runtime type name without importing the DTO's defining module."""

    role: RuntimeTopologyRole
    """Actor, supervision, provenance, or structural ownership."""

    shape: tuple[int, ...] | None = None
    """Tensor-like shape, when available."""

    dtype: str | None = None
    """Tensor-like dtype, when available."""

    device: str | None = None
    """Tensor-like device, when available."""

    context: tuple[str, ...] = ()
    """Mask, padding, and axis interpretation attached to the field."""

    @property
    def node_id(self) -> str:
        """Return the runtime path as the stable node identifier."""

        return self.path

    @property
    def label(self) -> str:
        """Return the final path segment used in compact trees."""

        return self.path.rsplit(".", 1)[-1]

    @property
    def kind(self) -> str:
        """Return the inspected Python type as the structural kind."""

        return self.python_type

    @property
    def status(self) -> TopologyStatus:
        """Runtime fields are materialized by construction."""

        return "materialized"

    def to_row(self) -> dict[str, object]:
        """Return one deterministic table row."""

        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "path": self.path,
            "python_type": self.python_type,
            "role": self.role,
            "status": self.status,
            "shape": None if self.shape is None else list(self.shape),
            "dtype": self.dtype,
            "device": self.device,
            "context": list(self.context),
        }


@dataclass(frozen=True, slots=True)
class RuntimeTopologyEdge:
    """One parent-child relationship in a nested runtime DTO."""

    source: str
    target: str
    relation: Literal["contains"] = "contains"

    @property
    def status(self) -> TopologyStatus:
        """Runtime nesting is embedded in the inspected object."""

        return "embedded"

    @property
    def evidence(self) -> None:
        """Runtime containment needs no additional evidence payload."""

        return None

    def to_row(self) -> dict[str, object]:
        """Return one deterministic relationship row."""

        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class RuntimeTopology:
    """Immutable shape/type topology for one runtime DTO."""

    nodes: tuple[RuntimeTopologyNode, ...]
    edges: tuple[RuntimeTopologyEdge, ...]

    def node_rows(self) -> list[dict[str, object]]:
        """Return deterministic DTO field rows."""

        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, object]]:
        """Return deterministic nesting relationships."""

        return [edge.to_row() for edge in self.edges]

    def tree_text(self) -> str:
        """Render a compact field tree with tensor metadata."""

        lines: list[str] = []
        for node in self.nodes:
            depth = node.path.count(".") + node.path.count("[")
            tensor = ""
            if node.shape is not None:
                tensor = f" shape={list(node.shape)} dtype={node.dtype} device={node.device}"
            context = f" ({'; '.join(node.context)})" if node.context else ""
            lines.append(f"{'  ' * depth}{node.path.rsplit('.', 1)[-1]}: {node.python_type}{tensor}{context}")
        return "\n".join(lines)

    def diagram_dot(self) -> None:
        """Runtime snapshots currently have no Graphviz projection."""

        return None


def build_runtime_topology(
    value: object,
    *,
    root_name: str = "sample",
    max_sequence_items: int = 4,
) -> RuntimeTopology:
    """Summarize a nested dataclass, tensor, mapping, or sequence.

    The adapter uses structural inspection only. In particular, it does not
    import QH DTOs, PyTorch, or EFM3D types. Tensor wrappers such as ``PoseTW``
    are recognized through their public ``tensor()`` projection.

    Args:
        value: Runtime DTO or nested value to inspect.
        root_name: Stable root label used in paths.
        max_sequence_items: Maximum sequence entries expanded at each level.

    Returns:
        Immutable nodes and containment relationships.
    """

    if max_sequence_items < 1:
        raise ValueError("max_sequence_items must be at least one.")
    nodes: list[RuntimeTopologyNode] = []
    edges: list[RuntimeTopologyEdge] = []
    root_type = type(value).__name__
    is_padded_batch = root_type.endswith("Batch")

    def visit(item: object, path: str, parent: str | None) -> None:
        role = _role_for_path(path)
        tensor_value = _tensor_projection(item)
        shape, dtype, device = _tensor_metadata(tensor_value)
        nodes.append(
            RuntimeTopologyNode(
                path=path,
                python_type=type(item).__name__,
                role=role,
                shape=shape,
                dtype=dtype,
                device=device,
                context=_field_context(path, shape=shape, is_padded_batch=is_padded_batch),
            )
        )
        if parent is not None:
            edges.append(RuntimeTopologyEdge(parent, path))
        if tensor_value is not None:
            return
        if _is_dataclass_instance(item):
            for field in fields(item):
                visit(getattr(item, field.name), f"{path}.{field.name}", path)
            return
        if isinstance(item, Mapping):
            for key in sorted(item, key=lambda entry: str(entry)):
                visit(item[key], f"{path}.{key}", path)
            return
        if _is_expandable_sequence(item):
            for index, child in enumerate(item[:max_sequence_items]):
                visit(child, f"{path}[{index}]", path)

    visit(value, root_name, None)
    return RuntimeTopology(tuple(nodes), tuple(edges))


def _tensor_projection(value: object) -> object | None:
    if _looks_tensor_like(value):
        return value
    tensor = getattr(value, "tensor", None)
    if not callable(tensor):
        return None
    try:
        projected = tensor()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return projected if _looks_tensor_like(projected) else None


def _looks_tensor_like(value: object) -> bool:
    return all(hasattr(value, name) for name in ("shape", "dtype"))


def _tensor_metadata(value: object | None) -> tuple[tuple[int, ...] | None, str | None, str | None]:
    if value is None:
        return None, None, None
    try:
        shape = tuple(int(size) for size in value.shape)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        shape = None
    dtype = str(getattr(value, "dtype", None))
    device_value = getattr(value, "device", None)
    return shape, None if dtype == "None" else dtype, None if device_value is None else str(device_value)


def _role_for_path(path: str) -> RuntimeTopologyRole:
    segments = path.replace("[", ".").split(".")
    if "inputs" in segments:
        return "actor-visible"
    if "supervision" in segments:
        return "oracle/evaluation"
    if "lineage" in segments:
        return "provenance"
    return "structure"


def _field_context(
    path: str,
    *,
    shape: tuple[int, ...] | None,
    is_padded_batch: bool,
) -> tuple[str, ...]:
    name = path.rsplit(".", 1)[-1]
    context: list[str] = []
    if is_padded_batch and shape:
        context.append("leading B axis; S/N axes may contain collation padding")
    meanings = {
        "actor_action_mask": "hard actor-valid candidate mask",
        "q_train_mask": "finite actor-valid Oracle supervision mask",
        "row_train_mask": "selected-transition loss gate; distinct from q_train_mask",
        "step_mask": "candidate-bearing state mask and batch padding gate",
        "previous_selected_mask": "right-shifted history presence mask",
        "invalid_reason_bitset": "hard-invalid reason flags; not a low-value label",
    }
    if name in meanings:
        context.append(meanings[name])
    elif name.endswith("_mask"):
        context.append("mask")
    if name in {"candidate_position_id", "previous_selected_position_id", "candidate_row_id"}:
        context.append("negative values denote padding")
    return tuple(context)


def _is_dataclass_instance(value: object) -> TypeGuard[_DataclassInstance]:
    """Narrow ``value`` to a non-class dataclass instance."""

    return is_dataclass(value) and not isinstance(value, type)


def _is_expandable_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """Narrow collections that are safe to inspect by bounded slicing."""

    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


__all__ = [
    "RuntimeTopology",
    "RuntimeTopologyEdge",
    "RuntimeTopologyNode",
    "RuntimeTopologyRole",
    "build_runtime_topology",
]
