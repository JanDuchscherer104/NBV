"""Metadata-only physical topology for VIN and rollout Zarr stores."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import msgspec
import numpy as np
import zarr
from rich.tree import Tree

from ..data_handling.offline.format import VinOfflineManifest
from ..utils.fingerprints import stable_msgspec_hash
from ..utils.rich_summary import rich_summary
from .contracts import TopologyRole, TopologyStatus

NativeLayoutRole = TopologyRole
"""Scientific ownership class used only by native-layout presentation."""

_NATIVE_ROLE_COLORS: dict[NativeLayoutRole, str] = {
    "actor-visible": "#1565c0",
    "oracle/evaluation": "#ef6c00",
    "derived training data": "#7b1fa2",
    "provenance": "#00897b",
    "structure": "#546e7a",
    "error": "#c62828",
}
_NATIVE_ROLE_LABELS: dict[NativeLayoutRole, str] = {
    "actor-visible": "Actor-visible VIN data",
    "oracle/evaluation": "Oracle / GT data",
    "derived training data": "Q_H model inputs",
    "provenance": "Root and replay metadata",
    "structure": "Physical structure",
    "error": "Blocked or missing metadata",
}


@dataclass(frozen=True, slots=True)
class NativeDatasetLayoutNode:
    """One physical metadata node in a selected training-data layout."""

    node_id: str
    """Stable catalog-local identifier."""

    label: str
    """Display label for the native hierarchy."""

    kind: Literal["store", "file", "group", "array", "error"]
    """Physical metadata kind."""

    path: str
    """Absolute filesystem path represented by this node."""

    details: dict[str, Any] = field(default_factory=dict)
    """Small metadata payload, including array dtype, shape, and chunks."""

    role: NativeLayoutRole = "provenance"
    """Scientific ownership used for semantic presentation colors."""

    @property
    def status(self) -> TopologyStatus:
        """Return whether the represented metadata is locally available."""

        if self.kind == "error" or self.details.get("missing"):
            return "missing"
        return "materialized"

    def to_row(self) -> dict[str, object]:
        """Return one deterministic renderer row."""

        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "path": self.path,
            "role": self.role,
            "status": self.status,
            **dict(sorted(self.details.items())),
        }

    def tree_label(self) -> str:
        """Return the compact label shown in the complete native tree."""

        if self.kind != "array":
            return self.label
        dtype = self.details.get("dtype", "unknown")
        shape = self.details.get("shape", "unknown")
        chunks = self.details.get("chunks", "unknown")
        path = self.details.get("relative_path", self.label)
        return f"{path}  dtype={dtype} shape={shape} chunks={chunks}"


@dataclass(frozen=True, slots=True)
class NativeDatasetLayoutEdge:
    """One physical containment or declared relational edge."""

    source: str
    """Origin node identifier."""

    target: str
    """Destination node identifier."""

    relation: str
    """Containment or schema-declared reference relation."""

    status: TopologyStatus = "resolved"
    """Whether the relationship can contribute to the selected training bundle."""

    evidence: str | None = None
    """Optional manifest hash or other compact provenance evidence."""

    def to_row(self) -> dict[str, object]:
        """Return one deterministic renderer row."""

        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "status": self.status,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class NativeDatasetLayout:
    """Complete metadata-only layout for one VIN root and rollout selection."""

    nodes: tuple[NativeDatasetLayoutNode, ...]
    """All physical metadata nodes in deterministic path order."""

    edges: tuple[NativeDatasetLayoutEdge, ...]
    """All containment and declared relational edges in deterministic order."""

    def node_rows(self) -> list[dict[str, object]]:
        """Return deterministic physical metadata rows."""

        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, object]]:
        """Return deterministic physical relationship rows."""

        return [edge.to_row() for edge in self.edges]

    def _children(self) -> tuple[dict[str, list[NativeDatasetLayoutNode]], dict[str, NativeDatasetLayoutNode]]:
        """Return deterministic physical containment indexes."""

        children: dict[str, list[NativeDatasetLayoutNode]] = {}
        node_by_id = {node.node_id: node for node in self.nodes}
        for edge in self.edges:
            if edge.relation == "contains" and edge.source in node_by_id and edge.target in node_by_id:
                children.setdefault(edge.source, []).append(node_by_id[edge.target])
        for entries in children.values():
            entries.sort(key=lambda node: (node.kind != "group", node.label, node.path))
        return children, node_by_id

    def _tree_payload(self) -> tuple[dict[str, Any], dict[tuple[str, ...], NativeLayoutRole]]:
        """Build one metadata-only nested mapping for the shared Rich renderer."""

        children, _node_by_id = self._children()

        role_by_path: dict[tuple[str, ...], NativeLayoutRole] = {}

        def visit(node: NativeDatasetLayoutNode, tree_path: tuple[str, ...]) -> Any:
            role_by_path[tree_path] = node.role
            payload: dict[str, Any] = {}
            for child in children.get(node.node_id, []):
                payload[child.label] = visit(child, tree_path + (child.label,))
            if node.kind == "array":
                payload.update(
                    {
                        "dtype": str(node.details.get("dtype", "unknown")),
                        "shape": str(node.details.get("shape", "unknown")),
                        "chunks": str(node.details.get("chunks", "unknown")),
                    }
                )
            if node.kind == "error":
                payload["error"] = str(node.details.get("error", "metadata unavailable"))
            return payload or ""

        roots = sorted((node for node in self.nodes if node.kind == "store"), key=lambda node: node.path)
        payload = {node.label: visit(node, (node.label,)) for node in roots}
        for node in sorted((node for node in self.nodes if node.kind == "error"), key=lambda node: node.path):
            label = f"! {node.label}"
            payload.setdefault(label, visit(node, (label,)))
        return payload, role_by_path

    def rich_tree(self, *, is_print: bool = False) -> Tree:
        """Build the shared Rich tree for interactive terminal consumers."""

        payload, _role_by_path = self._tree_payload()

        return rich_summary(
            payload,
            root_label="Native training layout",
            is_print=is_print,
        )

    def tree_text(self) -> str:
        """Render the native containment tree without flattening dotted paths."""

        children, _node_by_id = self._children()
        lines: list[str] = []

        def visit(node: NativeDatasetLayoutNode, prefix: str = "") -> None:
            lines.append(f"{prefix}{node.tree_label()}")
            for child in children.get(node.node_id, []):
                visit(child, prefix=f"{prefix}  ")

        roots = sorted((node for node in self.nodes if node.kind == "store"), key=lambda node: node.path)
        for root in roots:
            visit(root)
        for node in sorted((node for node in self.nodes if node.kind == "error"), key=lambda node: node.path):
            if node.node_id not in {child.node_id for entries in children.values() for child in entries}:
                lines.append(f"! {node.tree_label()}")
        return "\n".join(lines)

    def graphviz_dot(self) -> str:
        """Render an orientation-first diagram while retaining the full raw tree separately.

        Groups containing only array fields are shown as a single leaf. This
        keeps a data class such as ``oracle.p3d`` legible in the diagram while
        :meth:`tree_text` remains the complete source of field names, shapes,
        dtypes, and chunking.
        """

        children, node_by_id = self._children()
        collapsed_groups = {
            node_id
            for node_id, entries in children.items()
            if entries and all(entry.kind == "array" for entry in entries)
        }
        hidden_arrays = {child.node_id for group_id in collapsed_groups for child in children[group_id]}
        parent_by_hidden_array = {
            child.node_id: group_id for group_id in collapsed_groups for child in children[group_id]
        }
        visible_nodes = [node for node in self.nodes if node.node_id not in hidden_arrays]

        def projected_node_id(node_id: str) -> str:
            return parent_by_hidden_array.get(node_id, node_id)

        projected_edges: list[NativeDatasetLayoutEdge] = []
        seen_edges: set[tuple[str, str, str, str]] = set()
        for edge in self.edges:
            source = projected_node_id(edge.source)
            target = projected_node_id(edge.target)
            if source == target:
                continue
            key = (source, target, edge.relation, edge.status)
            if key in seen_edges:
                continue
            seen_edges.add(key)
            projected_edges.append(NativeDatasetLayoutEdge(source, target, edge.relation, edge.status, edge.evidence))

        def node_label(node: NativeDatasetLayoutNode) -> str:
            if node.node_id not in collapsed_groups:
                return node.tree_label()
            count = len(children[node.node_id])
            field_word = "field" if count == 1 else "fields"
            return f"{node.label}\\n{count} {field_word}; full details in raw tree"

        def node_line(node: NativeDatasetLayoutNode) -> str:
            label = _dot_escape(node_label(node))
            color = _NATIVE_ROLE_COLORS["error" if node.kind == "error" else node.role]
            shape = "folder" if node.kind in {"store", "group"} else "box"
            return (
                f'{_dot_id(node.node_id)} [label="{label}", color="{color}", fontcolor="{color}", '
                f'penwidth="2.2", fontsize="16", margin="0.22,0.14", shape="{shape}"];'
            )

        lines = [
            "digraph native_layout {",
            'rankdir="LR";',
            'graph [bgcolor="transparent", pad="0.65", nodesep="0.7", ranksep="1.35", newrank="true"];',
            'node [style="rounded,filled", fillcolor="#ffffff", fontname="Helvetica"];',
            'edge [fontname="Helvetica", fontsize="13", penwidth="1.8"];',
        ]
        core_nodes = [
            node for node in visible_nodes if node.role in {"actor-visible", "derived training data", "provenance"}
        ]
        auxiliary_nodes = [node for node in visible_nodes if node.role in {"oracle/evaluation", "structure", "error"}]
        for cluster_id, label, color, nodes in (
            ("training", "Core training data: VIN inputs, replay, and Q_H", "#90caf9", core_nodes),
            ("auxiliary", "Auxiliary and privileged supervision: Oracle / GT", "#ffcc80", auxiliary_nodes),
        ):
            lines.append(
                f'subgraph cluster_{cluster_id} {{ label="{label}"; color="{color}"; '
                'penwidth="2.6"; style="rounded"; fontsize="19"; fontname="Helvetica";'
            )
            lines.extend(node_line(node) for node in nodes)
            lines.append("}")
        for edge in projected_edges:
            target_node = node_by_id.get(edge.target)
            target_role = target_node.role if target_node is not None else "provenance"
            color = "#c62828" if edge.status != "resolved" else _NATIVE_ROLE_COLORS[target_role]
            style = "dashed" if edge.status != "resolved" else "solid"
            lines.append(
                f"{_dot_id(edge.source)} -> {_dot_id(edge.target)} "
                f'[label="{_dot_escape(edge.relation)}", color="{color}", fontcolor="{color}", style="{style}"];'
            )
        lines.append("}")
        return "\n".join(lines)

    def diagram_dot(self) -> str:
        """Return the compatibility Graphviz projection for shared rendering."""

        return self.graphviz_dot()


class _NativeLayoutBuilder:
    """Collect deterministic native-layout metadata without reading array payloads."""

    def __init__(self) -> None:
        self.nodes: dict[str, NativeDatasetLayoutNode] = {}
        self.edges: list[NativeDatasetLayoutEdge] = []

    def node(self, node: NativeDatasetLayoutNode) -> None:
        self.nodes.setdefault(node.node_id, node)

    def edge(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        status: Literal["resolved", "blocked", "missing"] = "resolved",
        evidence: str | None = None,
    ) -> None:
        edge = NativeDatasetLayoutEdge(source, target, relation, status, evidence)
        if edge not in self.edges:
            self.edges.append(edge)

    def build(self) -> NativeDatasetLayout:
        return NativeDatasetLayout(
            nodes=tuple(sorted(self.nodes.values(), key=lambda node: (node.path, node.node_id))),
            edges=tuple(sorted(self.edges, key=lambda edge: (edge.source, edge.target, edge.relation))),
        )


def build_native_dataset_layout(
    *,
    root_store_dir: Path | str,
    rollout_store_dirs: Sequence[Path | str],
    rollout_included: dict[str, bool] | None = None,
    selected_vin_shard: str | None = None,
) -> NativeDatasetLayout:
    """Catalog the selected physical Zarr stores and authoritative joins.

    The catalog opens only Zarr group and array metadata. It intentionally does
    not slice arrays, enumerate compressed chunks, or create a synthetic merged
    store. VIN shard arrays and rollout arrays remain distinct physical roots.

    Args:
        root_store_dir: Immutable VIN offline-store root selected for training.
        rollout_store_dirs: Explicit rollout-store roots selected beside it.
        rollout_included: Optional path-to-training-inclusion map from bundle
            validation. False entries remain visible through blocked lineage
            edges.
        selected_vin_shard: Optional VIN manifest ``relative_dir`` to show.
            When omitted, every shard remains visible for complete inspection.
    """

    builder = _NativeLayoutBuilder()
    root = Path(root_store_dir).expanduser().resolve()
    root_id, manifest_hash = _add_native_vin_store(builder, root, selected_vin_shard=selected_vin_shard)
    included = rollout_included or {}
    for rollout in _normalized_paths(rollout_store_dirs):
        rollout_id = _add_native_rollout_store(builder, rollout)
        allowed = included.get(rollout.as_posix(), _native_rollout_matches_root(rollout, manifest_hash))
        if rollout_id is None:
            continue
        builder.edge(
            root_id,
            rollout_id,
            "VIN manifest lineage",
            status="resolved" if allowed else "blocked",
            evidence=manifest_hash,
        )
        _add_declared_rollout_reference_edges(builder, rollout_id)
    return builder.build()


def _native_rollout_matches_root(rollout_dir: Path, manifest_hash: str | None) -> bool:
    """Return whether one rollout manifest explicitly references the VIN root."""

    if manifest_hash is None:
        return False
    try:
        manifest = _read_json_object(rollout_dir / "manifest.json")
    except (OSError, ValueError, TypeError):
        return False
    return manifest_hash in _source_manifest_hashes(manifest)


def _add_native_vin_store(
    builder: _NativeLayoutBuilder,
    store_dir: Path,
    *,
    selected_vin_shard: str | None,
) -> tuple[str, str | None]:
    store_id = _native_id("vin", store_dir)
    builder.node(
        NativeDatasetLayoutNode(
            store_id,
            f"VIN offline: {store_dir.name}",
            "store",
            store_dir.as_posix(),
            role="provenance",
        )
    )
    manifest_path = store_dir / "manifest.json"
    manifest_hash: str | None = None
    try:
        manifest = VinOfflineManifest.read(manifest_path)
        manifest_hash = stable_msgspec_hash(manifest)
        _add_native_file(builder, store_id, manifest_path, details={"manifest_hash": manifest_hash})
    except (OSError, ValueError, TypeError, msgspec.MsgspecError) as exc:
        _add_native_error(builder, store_id, manifest_path, exc)
        return store_id, None

    _add_native_file(builder, store_id, store_dir / "sample_index.jsonl")
    splits_dir = store_dir / "splits"
    splits_id = _add_native_group(builder, store_id, splits_dir, label="splits", role="provenance")
    for path in sorted(splits_dir.glob("*.npy"), key=lambda item: item.as_posix()):
        details = _npy_metadata(path)
        _add_native_file(builder, splits_id, path, details=details, role="provenance")
    for shard in sorted(manifest.shards, key=lambda item: item.relative_dir):
        if selected_vin_shard is not None and shard.relative_dir != selected_vin_shard:
            continue
        shard_dir = store_dir / shard.relative_dir
        shard_id = _add_native_group(builder, store_id, shard_dir, label=shard.relative_dir, role="actor-visible")
        _add_native_zarr_group(builder, shard_id, shard_dir, root_label="zarr", base_role="actor-visible")
    return store_id, manifest_hash


def _add_native_rollout_store(builder: _NativeLayoutBuilder, store_dir: Path) -> str:
    store_id = _native_id("rollout", store_dir)
    builder.node(
        NativeDatasetLayoutNode(
            store_id, f"Rollout Zarr: {store_dir.name}", "store", store_dir.as_posix(), role="provenance"
        )
    )
    _add_native_file(builder, store_id, store_dir / "manifest.json", role="provenance")
    _add_native_zarr_group(builder, store_id, store_dir, root_label="zarr", base_role="provenance")
    return store_id


def _add_native_zarr_group(
    builder: _NativeLayoutBuilder,
    parent_id: str,
    store_dir: Path,
    *,
    root_label: str,
    base_role: NativeLayoutRole,
) -> bool:
    """Add one complete Zarr group hierarchy using metadata-only access."""

    try:
        root = zarr.open_group(store=zarr.storage.LocalStore(str(store_dir), read_only=True), mode="r")
    except Exception as exc:  # Zarr normalizes several backend-specific failures.
        _add_native_error(builder, parent_id, store_dir / "zarr.json", exc)
        return False

    root_id = _native_id("group", store_dir)
    if root_id not in builder.nodes:
        root_id = _add_native_group(builder, parent_id, store_dir, label=root_label, role=base_role)

    def visit(group: Any, group_id: str, prefix: str) -> None:
        for name, member in sorted(group.members(), key=lambda item: item[0]):
            path = f"{prefix}/{name}" if prefix else name
            member_path = store_dir / path
            if hasattr(member, "members"):
                child_id = _add_native_group(
                    builder, group_id, member_path, label=name, role=_native_role_for_path(base_role, path)
                )
                visit(member, child_id, path)
                continue
            node_id = _native_id("array", store_dir / path)
            builder.node(
                NativeDatasetLayoutNode(
                    node_id,
                    name,
                    "array",
                    member_path.as_posix(),
                    {
                        "relative_path": path,
                        "dtype": str(member.dtype),
                        "shape": list(member.shape),
                        "chunks": list(member.chunks) if member.chunks is not None else None,
                    },
                    _native_role_for_path(base_role, path),
                )
            )
            builder.edge(group_id, node_id, "contains")

    visit(root, root_id, "")
    return True


def _add_declared_rollout_reference_edges(builder: _NativeLayoutBuilder, store_id: str) -> None:
    """Add only schema-defined replay references that are physically present."""

    store_path = next(node.path for node in builder.nodes.values() if node.node_id == store_id)
    pairs = (
        ("sources/source_row_id", "rollouts/source_row_id", "source row"),
        ("targets/target_row_id", "rollouts/target_row_id", "target row"),
        ("rollouts/rollout_row_id", "lineage/rollout_row_id", "rollout lineage"),
        ("rollouts/rollout_row_id", "steps/rollout_row_id", "rollout steps"),
        ("steps/step_row_id", "candidates/step_row_id", "step candidates"),
        ("candidates/candidate_row_id", "selected_depth/candidate_row_id", "selected depth"),
        ("steps/step_row_id", "q_h/state_step_row_id", "derived Q_H state"),
        ("candidates/candidate_row_id", "q_h/candidate_row_id", "derived Q_H actions"),
    )
    for source_path, target_path, relation in pairs:
        source = _native_id("array", Path(store_path) / source_path)
        target = _native_id("array", Path(store_path) / target_path)
        if source in builder.nodes and target in builder.nodes:
            builder.edge(source, target, relation)


def _native_role_for_path(base_role: NativeLayoutRole, path: str) -> NativeLayoutRole:
    """Classify a native array/group without changing its storage semantics."""

    first = path.split("/", 1)[0]
    if first == "q_h":
        return "derived training data"
    if first in {"oracle", "gt", "gt_data", "targets", "selected_depth"}:
        return "oracle/evaluation"
    return base_role


def _add_native_group(
    builder: _NativeLayoutBuilder, parent_id: str, path: Path, *, label: str, role: NativeLayoutRole
) -> str:
    node_id = _native_id("group", path)
    builder.node(NativeDatasetLayoutNode(node_id, label, "group", path.as_posix(), role=role))
    builder.edge(parent_id, node_id, "contains")
    return node_id


def _add_native_file(
    builder: _NativeLayoutBuilder,
    parent_id: str,
    path: Path,
    *,
    details: dict[str, Any] | None = None,
    role: NativeLayoutRole = "provenance",
) -> None:
    node_id = _native_id("file", path)
    payload = dict(details or {})
    if not path.is_file():
        payload["missing"] = True
    builder.node(NativeDatasetLayoutNode(node_id, path.name, "file", path.as_posix(), payload, role))
    builder.edge(parent_id, node_id, "contains", status="resolved" if path.is_file() else "missing")


def _add_native_error(builder: _NativeLayoutBuilder, parent_id: str, path: Path, exc: Exception) -> None:
    node_id = _native_id("error", path)
    builder.node(
        NativeDatasetLayoutNode(
            node_id,
            f"unreadable: {path.name}",
            "error",
            path.as_posix(),
            {"error": f"{type(exc).__name__}: {exc}"},
            "error",
        )
    )
    builder.edge(parent_id, node_id, "metadata unavailable", status="missing")


def _npy_metadata(path: Path) -> dict[str, Any]:
    try:
        array = np.load(path, mmap_mode="r", allow_pickle=False)
    except (OSError, ValueError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"dtype": str(array.dtype), "shape": list(array.shape)}


def _native_id(kind: str, path: Path) -> str:
    return f"{kind}:{path.as_posix()}"


def _dot_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _dot_id(value: str) -> str:
    return f'"{_dot_escape(value)}"'


def _normalized_paths(paths: Sequence[Path | str]) -> list[Path]:
    return sorted(
        {Path(path).expanduser().resolve() for path in paths},
        key=lambda path: path.as_posix(),
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object at {path}.")
    return payload


def _source_manifest_hashes(manifest: dict[str, Any]) -> list[str]:
    config_hashes = manifest.get("config_hashes")
    if not isinstance(config_hashes, dict):
        return []
    hashes = config_hashes.get("source_manifest")
    if not isinstance(hashes, list):
        return []
    return sorted({str(value) for value in hashes if value})


__all__ = [
    "NativeDatasetLayout",
    "NativeDatasetLayoutEdge",
    "NativeDatasetLayoutNode",
    "NativeLayoutRole",
    "build_native_dataset_layout",
]
