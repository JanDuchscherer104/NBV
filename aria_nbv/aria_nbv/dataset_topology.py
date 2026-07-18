"""Read-only cross-store topology projections for scientific dataset inspection.

The topology joins rollout lineage to immutable VIN offline stores by the
canonical VIN manifest hash. It reads manifests, indexes, split filenames, and
artifact existence only; it never opens heavy candidate arrays or mutates a
store. Streamlit, Rich CLIs, and JSON exporters consume the same presentation-
neutral nodes, edges, modality rows, and selected-source evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import msgspec

from .configs import PathConfig
from .configs.path_config import PROJECT_ROOT
from .data_handling.identifiers import compact_ase_atek_sample_id
from .data_handling.offline.format import VinOfflineIndexRecord, VinOfflineManifest
from .utils.fingerprints import stable_msgspec_hash
from .utils.rich_summary import capture_tree, rich_summary

TopologyResolution = Literal[
    "embedded",
    "resolved pointer",
    "lineage only",
    "inferred path",
    "missing",
    "ambiguous",
]
"""How one topology edge was established without inventing physical linkage."""

TopologyRole = Literal[
    "actor-visible",
    "oracle/evaluation",
    "derived training data",
    "provenance",
]
"""Scientific role of one persisted or referenced modality."""

TopologyAvailability = Literal["materialized", "referenced", "optional", "absent"]
"""Whether a topology node is physically present or only declared/referenced."""


@dataclass(frozen=True, slots=True)
class DatasetTopologyNode:
    """One store, artifact, identity, or modality in the cross-store graph."""

    node_id: str
    """Stable graph-local identifier."""

    label: str
    """Compact human-readable label."""

    kind: str
    """Structural kind such as ``rollout store``, ``VIN manifest``, or ``mesh``."""

    role: TopologyRole
    """Scientific evidence boundary represented by this node."""

    availability: TopologyAvailability
    """Physical or declared availability in the inspected local workspace."""

    path: str | None = None
    """Resolved local path when a meaningful path is known."""

    modality: str | None = None
    """Modality-matrix label; ``None`` excludes structural-only nodes."""

    details: dict[str, Any] = field(default_factory=dict)
    """Small JSON-compatible evidence payload; never contains heavy arrays."""

    def to_row(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible node row."""

        return {
            "node_id": self.node_id,
            "label": self.label,
            "kind": self.kind,
            "role": self.role,
            "availability": self.availability,
            "path": self.path,
            "modality": self.modality,
            "details": dict(sorted(self.details.items())),
        }


@dataclass(frozen=True, slots=True)
class DatasetTopologyEdge:
    """One classified relationship between two topology nodes."""

    source: str
    """Source node identifier."""

    target: str
    """Target node identifier."""

    relation: str
    """Domain relationship, for example ``resolves manifest hash``."""

    resolution: TopologyResolution
    """Evidence strength and local resolution outcome."""

    evidence: str | None = None
    """Hash, path, identity, or concise reason supporting the classification."""

    def to_row(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible edge row."""

        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "resolution": self.resolution,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class DatasetTopology:
    """Immutable aggregate topology and selected-source drill-down projection."""

    nodes: tuple[DatasetTopologyNode, ...]
    """Graph nodes in deterministic construction order."""

    edges: tuple[DatasetTopologyEdge, ...]
    """Classified graph edges in deterministic construction order."""

    sources: tuple[dict[str, Any], ...] = ()
    """Lightweight rollout source rows augmented with VIN resolution evidence."""

    selected_source_row_id: int | None = None
    """Optional rollout source row expanded into exact sample and artifact nodes."""

    def node_rows(self) -> list[dict[str, Any]]:
        """Return complete graph-node rows without heavy payload data."""

        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, Any]]:
        """Return complete classified graph-edge rows."""

        return [edge.to_row() for edge in self.edges]

    def aggregate_node_rows(self) -> list[dict[str, Any]]:
        """Return graph nodes with shard-repeated VIN blocks grouped by role."""

        nodes, _edges = _aggregate_graph(self.nodes, self.edges)
        return [node.to_row() for node in nodes]

    def aggregate_edge_rows(self) -> list[dict[str, Any]]:
        """Return classified edges for :meth:`aggregate_node_rows`."""

        _nodes, edges = _aggregate_graph(self.nodes, self.edges)
        return [edge.to_row() for edge in edges]

    def modality_rows(self) -> list[dict[str, Any]]:
        """Return the actor/oracle/derived/provenance modality matrix."""

        return [
            {
                "modality": node.modality,
                "kind": node.kind,
                "role": node.role,
                "availability": node.availability,
                "path": node.path,
                "details": dict(sorted(node.details.items())),
            }
            for node in self.nodes
            if node.modality is not None
        ]

    def source_rows(self) -> list[dict[str, Any]]:
        """Return all lightweight source identities for drill-down selection."""

        return [dict(row) for row in self.sources]

    def sankey_data(self) -> dict[str, dict[str, list[Any]]]:
        """Return Plotly ``go.Sankey``-compatible node and link keyword data."""

        nodes, edges = _aggregate_graph(self.nodes, self.edges)
        node_index = {node.node_id: index for index, node in enumerate(nodes)}
        return {
            "node": {
                "label": [node.label for node in nodes],
                "customdata": [f"{node.kind} | {node.role} | {node.availability}" for node in nodes],
            },
            "link": {
                "source": [node_index[edge.source] for edge in edges],
                "target": [node_index[edge.target] for edge in edges],
                "value": [1 for _edge in edges],
                "label": [edge.relation for edge in edges],
                "customdata": [edge.resolution for edge in edges],
            },
        }

    def to_jsonable(self) -> dict[str, Any]:
        """Return the complete deterministic topology evidence projection."""

        return {
            "selected_source_row_id": self.selected_source_row_id,
            "nodes": self.node_rows(),
            "edges": self.edge_rows(),
            "aggregate_nodes": self.aggregate_node_rows(),
            "aggregate_edges": self.aggregate_edge_rows(),
            "modalities": self.modality_rows(),
            "sources": self.source_rows(),
        }

    def plain_text_tree(self) -> str:
        """Render a compact Rich-compatible tree through :mod:`rich_summary`."""

        tree_payload: dict[str, Any] = {
            "Stores": {
                node.label: {
                    "kind": node.kind,
                    "availability": node.availability,
                    "path": node.path or "unresolved",
                }
                for node in self.nodes
                if node.kind in {"rollout store", "VIN manifest"}
            },
            "Relations": _resolution_counts(self.edges),
            "Modalities": {
                str(row["modality"]): {
                    "role": row["role"],
                    "availability": row["availability"],
                }
                for row in self.modality_rows()
            },
        }
        if self.selected_source_row_id is not None:
            selected = next(
                (row for row in self.sources if row.get("source_row_id") == self.selected_source_row_id),
                None,
            )
            if selected is not None:
                tree_payload[f"Selected source {self.selected_source_row_id}"] = dict(selected)
        tree = rich_summary(tree_payload, root_label="Dataset topology", is_print=False)
        return capture_tree(tree)


@dataclass(frozen=True, slots=True)
class _VinStoreSnapshot:
    store_dir: Path
    manifest: VinOfflineManifest | None
    manifest_hash: str | None
    index_records: tuple[VinOfflineIndexRecord, ...]
    error: str | None = None


class _TopologyPaths(Protocol):
    data_root: Path
    ase_meshes: Path
    processed_meshes: Path

    def resolve_mesh_path(self, scene_id: str) -> Path: ...


@dataclass(frozen=True, slots=True)
class _DefaultTopologyPaths:
    """Canonical path projections without PathConfig's directory creation."""

    data_root: Path = PROJECT_ROOT / ".data"
    ase_meshes: Path = PROJECT_ROOT / ".data" / "ase_meshes"
    processed_meshes: Path = PROJECT_ROOT / ".data" / "ase_meshes_processed"

    def resolve_mesh_path(self, scene_id: str) -> Path:
        return self.ase_meshes / f"scene_ply_{scene_id}.ply"


class _TopologyBuilder:
    def __init__(self) -> None:
        self.nodes: dict[str, DatasetTopologyNode] = {}
        self.edges: list[DatasetTopologyEdge] = []
        self.sources: list[dict[str, Any]] = []

    def node(self, node: DatasetTopologyNode) -> str:
        self.nodes.setdefault(node.node_id, node)
        return node.node_id

    def edge(
        self,
        source: str,
        target: str,
        relation: str,
        resolution: TopologyResolution,
        evidence: str | None = None,
    ) -> None:
        edge = DatasetTopologyEdge(source, target, relation, resolution, evidence)
        if edge not in self.edges:
            self.edges.append(edge)

    def build(self, *, selected_source_row_id: int | None) -> DatasetTopology:
        return DatasetTopology(
            nodes=tuple(self.nodes.values()),
            edges=tuple(self.edges),
            sources=tuple(self.sources),
            selected_source_row_id=selected_source_row_id,
        )


def discover_vin_store_dirs(root: Path | str) -> list[Path]:
    """Discover immutable VIN stores below ``root`` from their two index files.

    Discovery checks filenames only and does not validate or open shard arrays.
    Returned absolute paths are sorted for deterministic manifest-hash matching.
    """

    search_root = Path(root).expanduser().resolve()
    if not search_root.exists():
        return []
    stores = {
        manifest.parent.resolve()
        for manifest in search_root.rglob("manifest.json")
        if (manifest.parent / "sample_index.jsonl").is_file()
    }
    return sorted(stores, key=lambda path: path.as_posix())


def build_dataset_topology(
    *,
    rollout_store_dir: Path | str | None = None,
    vin_store_dirs: Sequence[Path | str] = (),
    path_config: PathConfig | None = None,
    selected_source_row_id: int | None = None,
    report_bundle_paths: Sequence[Path | str] = (),
    rerun_recording_paths: Sequence[Path | str] = (),
) -> DatasetTopology:
    """Build a read-only cross-store dataset and artifact topology.

    Args:
        rollout_store_dir: Optional rollout Zarr directory. Only its sidecar
            manifest and group markers are inspected.
        vin_store_dirs: Candidate VIN offline-store roots matched by canonical
            manifest hash. Pass :func:`discover_vin_store_dirs` output when the
            app should search a cache root.
        path_config: Filesystem resolver for ATEK and mesh locations.
        selected_source_row_id: Optional rollout source row to expand into its
            exact VIN sample, shard, scene, snippet, and mesh links.
        report_bundle_paths: Known evidence-bundle paths linked to the rollout.
        rerun_recording_paths: Known ``.rrd`` paths linked to the rollout.

    Returns:
        :class:`DatasetTopology` with aggregate graph rows, modality rows,
        selected-source evidence, JSON, Sankey, and Rich-tree projections.

    Notes:
        A matching identifier never implies a physical link. Exact unique
        manifest hashes become ``resolved pointer`` edges; duplicates are
        ``ambiguous`` and absent local artifacts remain ``missing``.
    """

    paths: _TopologyPaths = path_config or _DefaultTopologyPaths()
    vin_snapshots = [_read_vin_snapshot(path) for path in _normalized_paths(vin_store_dirs)]
    builder = _TopologyBuilder()
    inventory_snapshots = _inventory_snapshots(
        rollout_store_dir=rollout_store_dir,
        snapshots=vin_snapshots,
    )
    for snapshot in inventory_snapshots:
        _add_vin_store(builder, snapshot, paths=paths)

    if rollout_store_dir is not None:
        _add_rollout_store(
            builder,
            Path(rollout_store_dir).expanduser().resolve(),
            snapshots=vin_snapshots,
            paths=paths,
            selected_source_row_id=selected_source_row_id,
            report_bundle_paths=_normalized_paths(report_bundle_paths),
            rerun_recording_paths=_normalized_paths(rerun_recording_paths),
        )
    return builder.build(selected_source_row_id=selected_source_row_id)


def _normalized_paths(paths: Sequence[Path | str]) -> list[Path]:
    return sorted(
        {Path(path).expanduser().resolve() for path in paths},
        key=lambda path: path.as_posix(),
    )


def _inventory_snapshots(
    *,
    rollout_store_dir: Path | str | None,
    snapshots: list[_VinStoreSnapshot],
) -> list[_VinStoreSnapshot]:
    """Limit detailed VIN inventories to manifests referenced by a rollout."""

    if rollout_store_dir is None:
        return snapshots
    try:
        manifest = _read_json_object(Path(rollout_store_dir).expanduser().resolve() / "manifest.json")
    except (OSError, ValueError, TypeError):
        return []
    hashes = set(_source_manifest_hashes(manifest))
    return [snapshot for snapshot in snapshots if snapshot.manifest_hash in hashes]


def _read_vin_snapshot(store_dir: Path) -> _VinStoreSnapshot:
    try:
        manifest = VinOfflineManifest.read(store_dir / "manifest.json")
        records = tuple(VinOfflineIndexRecord.read_many(store_dir / "sample_index.jsonl"))
    except (OSError, ValueError, TypeError, msgspec.MsgspecError) as exc:
        return _VinStoreSnapshot(store_dir, None, None, (), f"{type(exc).__name__}: {exc}")
    return _VinStoreSnapshot(
        store_dir=store_dir,
        manifest=manifest,
        manifest_hash=stable_msgspec_hash(manifest),
        index_records=records,
    )


def _add_vin_store(
    builder: _TopologyBuilder,
    snapshot: _VinStoreSnapshot,
    *,
    paths: _TopologyPaths,
) -> None:
    store_id = _vin_id(snapshot.store_dir)
    availability: TopologyAvailability = "materialized" if snapshot.manifest is not None else "absent"
    builder.node(
        DatasetTopologyNode(
            store_id,
            f"VIN manifest: {snapshot.store_dir.name}",
            "VIN manifest",
            "provenance",
            availability,
            snapshot.store_dir.as_posix(),
            "VIN manifest",
            {
                "manifest_hash": snapshot.manifest_hash,
                "error": snapshot.error,
            },
        )
    )
    if snapshot.manifest is None:
        return

    _add_vin_index_nodes(builder, snapshot, store_id=store_id)
    _add_vin_block_nodes(builder, snapshot, store_id=store_id)
    _add_vin_source_roots(builder, snapshot, store_id=store_id, paths=paths)


def _add_vin_index_nodes(
    builder: _TopologyBuilder,
    snapshot: _VinStoreSnapshot,
    *,
    store_id: str,
) -> None:
    index_path = snapshot.store_dir / "sample_index.jsonl"
    index_id = f"{store_id}:sample-index"
    builder.node(
        DatasetTopologyNode(
            index_id,
            f"Sample index ({len(snapshot.index_records)})",
            "sample index",
            "provenance",
            _path_availability(index_path),
            index_path.as_posix(),
            "VIN sample index",
            {"rows": len(snapshot.index_records)},
        )
    )
    builder.edge(store_id, index_id, "contains sample index", _embedded_or_missing(index_path))

    split_paths = sorted((snapshot.store_dir / "splits").glob("*.npy"))
    splits_id = f"{store_id}:splits"
    builder.node(
        DatasetTopologyNode(
            splits_id,
            f"Split arrays ({len(split_paths)})",
            "split arrays",
            "provenance",
            "materialized" if split_paths else "absent",
            (snapshot.store_dir / "splits").as_posix(),
            "VIN split arrays",
            {"names": [path.stem for path in split_paths]},
        )
    )
    builder.edge(
        store_id,
        splits_id,
        "contains split arrays",
        "embedded" if split_paths else "missing",
    )

    shards = snapshot.manifest.shards if snapshot.manifest is not None else []
    shards_id = f"{store_id}:shards"
    shard_paths = [snapshot.store_dir / shard.relative_dir for shard in shards]
    builder.node(
        DatasetTopologyNode(
            shards_id,
            f"Immutable shards ({len(shards)})",
            "VIN shards",
            "provenance",
            _collection_availability(shard_paths),
            (snapshot.store_dir / "shards").as_posix(),
            "VIN immutable shards",
            {"count": len(shards)},
        )
    )
    builder.edge(
        store_id,
        shards_id,
        "contains immutable shards",
        _collection_resolution(shard_paths),
    )


def _add_vin_block_nodes(
    builder: _TopologyBuilder,
    snapshot: _VinStoreSnapshot,
    *,
    store_id: str,
) -> None:
    assert snapshot.manifest is not None
    blocks_by_name: dict[str, list[tuple[Path, bool]]] = {}
    for shard in snapshot.manifest.shards:
        shard_dir = snapshot.store_dir / shard.relative_dir
        for block in shard.blocks.values():
            for block_path in block.paths:
                blocks_by_name.setdefault(block.name, []).append((shard_dir / block_path, block.optional))

    for block_name, path_entries in sorted(blocks_by_name.items()):
        block_id = f"{store_id}:block:{block_name}"
        block_paths = [path for path, _optional in path_entries]
        builder.node(
            DatasetTopologyNode(
                block_id,
                block_name,
                "VIN block",
                _block_role(block_name),
                _collection_availability(block_paths),
                snapshot.store_dir.as_posix(),
                f"VIN block: {block_name}",
                {
                    "path_count": len(block_paths),
                    "optional": all(optional for _path, optional in path_entries),
                },
            )
        )
        builder.edge(
            store_id,
            block_id,
            "materializes block",
            _collection_resolution(block_paths),
        )

    flags = snapshot.manifest.materialized_blocks
    for field_name, label, role in (
        ("backbone", "VIN backbone evidence", "actor-visible"),
        ("depths", "VIN candidate depths", "oracle/evaluation"),
        ("candidate_pcs", "VIN candidate point clouds", "oracle/evaluation"),
        ("gt_obbs", "VIN GT OBB labels", "oracle/evaluation"),
        ("detected_obbs", "VIN detected OBBs", "actor-visible"),
        ("trajectory", "VIN trajectory context", "actor-visible"),
    ):
        present = bool(getattr(flags, field_name))
        node_id = f"{store_id}:flag:{field_name}"
        builder.node(
            DatasetTopologyNode(
                node_id,
                label,
                "VIN materialized-block flag",
                role,  # type: ignore[arg-type]
                "materialized" if present else "absent",
                snapshot.store_dir.as_posix(),
                label,
                {"declared_optional": True},
            )
        )
        builder.edge(
            store_id,
            node_id,
            "declares optional modality",
            "embedded" if present else "lineage only",
        )


def _add_vin_source_roots(
    builder: _TopologyBuilder,
    snapshot: _VinStoreSnapshot,
    *,
    store_id: str,
    paths: _TopologyPaths,
) -> None:
    assert snapshot.manifest is not None
    scenes = sorted({record.scene_id for record in snapshot.index_records})
    scene_id = f"{store_id}:ase-identities"
    builder.node(
        DatasetTopologyNode(
            scene_id,
            f"ASE scene/snippet identities ({len(scenes)}/{len(snapshot.index_records)})",
            "ASE identities",
            "provenance",
            "referenced",
            None,
            "ASE source identities",
            {"scene_count": len(scenes), "snippet_count": len(snapshot.index_records)},
        )
    )
    builder.edge(store_id, scene_id, "records source identities", "lineage only")

    atek_path, atek_resolution = _atek_root(snapshot.manifest, paths)
    atek_id = f"atek:{atek_path.as_posix()}"
    builder.node(
        DatasetTopologyNode(
            atek_id,
            f"ATEK root: {atek_path.name}",
            "ATEK root",
            "actor-visible",
            _path_availability(atek_path),
            atek_path.as_posix(),
            "ATEK source root",
        )
    )
    builder.edge(scene_id, atek_id, "locates ATEK source", atek_resolution, atek_path.as_posix())

    for label, root_path in (
        ("GT mesh root", paths.ase_meshes),
        ("Processed mesh root", paths.processed_meshes),
    ):
        mesh_root_id = f"mesh-root:{root_path.as_posix()}"
        builder.node(
            DatasetTopologyNode(
                mesh_root_id,
                label,
                "mesh root",
                "oracle/evaluation",
                _path_availability(root_path),
                root_path.as_posix(),
                label,
            )
        )
        builder.edge(
            scene_id,
            mesh_root_id,
            "infers mesh location",
            "inferred path" if root_path.exists() else "missing",
            f"PathConfig; scenes={','.join(scenes)}",
        )


def _add_rollout_store(
    builder: _TopologyBuilder,
    store_dir: Path,
    *,
    snapshots: list[_VinStoreSnapshot],
    paths: PathConfig,
    selected_source_row_id: int | None,
    report_bundle_paths: list[Path],
    rerun_recording_paths: list[Path],
) -> None:
    manifest_path = store_dir / "manifest.json"
    try:
        manifest = _read_json_object(manifest_path)
        manifest_error = None
    except (OSError, ValueError, TypeError) as exc:
        manifest = {}
        manifest_error = f"{type(exc).__name__}: {exc}"
    rollout_id = f"rollout:{store_dir.as_posix()}"
    builder.node(
        DatasetTopologyNode(
            rollout_id,
            f"Rollout store: {store_dir.name}",
            "rollout store",
            "provenance",
            "materialized" if manifest else "absent",
            store_dir.as_posix(),
            "Rollout store",
            {
                "schema_id": manifest.get("schema_id"),
                "schema_version": manifest.get("schema_version"),
                "error": manifest_error,
            },
        )
    )
    _add_rollout_payload_nodes(builder, rollout_id=rollout_id, store_dir=store_dir, manifest=manifest)
    _add_known_artifacts(
        builder,
        rollout_id=rollout_id,
        paths=report_bundle_paths,
        kind="evidence bundle",
        label="Evidence bundle",
        role="provenance",
    )
    _add_known_artifacts(
        builder,
        rollout_id=rollout_id,
        paths=rerun_recording_paths,
        kind="Rerun recording",
        label="Rerun recording",
        role="provenance",
    )
    _add_rollout_lineage(
        builder,
        rollout_id=rollout_id,
        manifest=manifest,
        snapshots=snapshots,
        paths=paths,
        selected_source_row_id=selected_source_row_id,
    )


def _add_rollout_payload_nodes(
    builder: _TopologyBuilder,
    *,
    rollout_id: str,
    store_dir: Path,
    manifest: dict[str, Any],
) -> None:
    root_attrs = manifest.get("root_attrs") if isinstance(manifest.get("root_attrs"), dict) else {}
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    payloads: tuple[tuple[str, str, TopologyRole, tuple[str, ...], bool, dict[str, Any]], ...] = (
        (
            "factual-tables",
            "Factual rollout tables",
            "provenance",
            ("sources", "rollouts", "steps", "candidates", "targets"),
            True,
            {"source": "canonical factual tables"},
        ),
        (
            "selected-depth",
            "Selected depth",
            "oracle/evaluation",
            ("selected_depth",),
            int(counts.get("selected_depths", root_attrs.get("num_selected_depths", 0)) or 0) > 0,
            {"privileged": True, "role": root_attrs.get("selected_depth_role")},
        ),
        (
            "target-eval-crops",
            "Target evaluation crops",
            "oracle/evaluation",
            ("target_eval_crops",),
            int(counts.get("target_eval_crops", root_attrs.get("target_eval_crops_num_rows", 0)) or 0) > 0,
            {"privileged": True, "role": root_attrs.get("target_eval_crops_role")},
        ),
        (
            "q-h",
            "Derived Q_H cache",
            "derived training data",
            ("q_h",),
            True,
            {"source_tables": root_attrs.get("q_h_source_tables")},
        ),
    )
    for suffix, label, role, group_names, has_rows, details in payloads:
        group_paths = [store_dir / name / "zarr.json" for name in group_names]
        resolution = _collection_resolution(group_paths)
        physically_present = any(path.exists() for path in group_paths)
        availability: TopologyAvailability
        if physically_present and has_rows:
            availability = "materialized"
        elif physically_present:
            availability = "optional"
        else:
            availability = "absent"
        node_id = f"{rollout_id}:{suffix}"
        builder.node(
            DatasetTopologyNode(
                node_id,
                label,
                "rollout payload",
                role,
                availability,
                store_dir.as_posix(),
                label,
                details,
            )
        )
        builder.edge(rollout_id, node_id, "contains rollout payload", resolution)


def _add_known_artifacts(
    builder: _TopologyBuilder,
    *,
    rollout_id: str,
    paths: list[Path],
    kind: str,
    label: str,
    role: TopologyRole,
) -> None:
    artifact_paths = paths or [None]
    for index, path in enumerate(artifact_paths):
        path_text = path.as_posix() if path is not None else None
        node_id = f"{rollout_id}:{kind}:{path_text or 'unresolved'}:{index}"
        builder.node(
            DatasetTopologyNode(
                node_id,
                label if path is None else f"{label}: {path.name}",
                kind,
                role,
                "materialized" if path is not None and path.exists() else "absent",
                path_text,
                label,
            )
        )
        builder.edge(
            rollout_id,
            node_id,
            f"produces {kind}",
            "resolved pointer" if path is not None and path.exists() else "missing",
            path_text,
        )


def _add_rollout_lineage(
    builder: _TopologyBuilder,
    *,
    rollout_id: str,
    manifest: dict[str, Any],
    snapshots: list[_VinStoreSnapshot],
    paths: _TopologyPaths,
    selected_source_row_id: int | None,
) -> None:
    source_rows = _rollout_source_rows(manifest)
    hashes = _source_manifest_hashes(manifest)
    aggregate_id = f"{rollout_id}:source-lineage"
    builder.node(
        DatasetTopologyNode(
            aggregate_id,
            f"Source lineage ({len(source_rows)} rows)",
            "rollout source lineage",
            "provenance",
            "materialized" if source_rows else "absent",
            None,
            "Rollout source lineage",
            {"manifest_hashes": hashes, "source_rows": len(source_rows)},
        )
    )
    builder.edge(rollout_id, aggregate_id, "records source lineage", "embedded" if source_rows else "missing")

    matches_by_hash = {
        manifest_hash: [snapshot for snapshot in snapshots if snapshot.manifest_hash == manifest_hash]
        for manifest_hash in hashes
    }
    if not hashes:
        missing_id = f"{rollout_id}:missing-source-manifest-hash"
        builder.node(
            DatasetTopologyNode(
                missing_id,
                "Missing VIN manifest hash",
                "unresolved pointer",
                "provenance",
                "absent",
            )
        )
        builder.edge(aggregate_id, missing_id, "resolves manifest hash", "missing", "no source manifest hash")

    for manifest_hash, matches in matches_by_hash.items():
        lineage_id = f"lineage:{manifest_hash}"
        builder.node(
            DatasetTopologyNode(
                lineage_id,
                f"VIN manifest hash: {manifest_hash}",
                "manifest hash lineage",
                "provenance",
                "referenced",
                None,
                "VIN manifest lineage",
                {"match_count": len(matches)},
            )
        )
        builder.edge(aggregate_id, lineage_id, "records manifest hash", "lineage only", manifest_hash)
        if not matches:
            missing_id = f"missing:vin:{manifest_hash}"
            builder.node(
                DatasetTopologyNode(
                    missing_id,
                    f"Unresolved VIN manifest: {manifest_hash}",
                    "unresolved pointer",
                    "provenance",
                    "absent",
                )
            )
            builder.edge(lineage_id, missing_id, "resolves manifest hash", "missing", manifest_hash)
        else:
            resolution: TopologyResolution = "resolved pointer" if len(matches) == 1 else "ambiguous"
            for match in matches:
                builder.edge(
                    lineage_id,
                    _vin_id(match.store_dir),
                    "resolves manifest hash",
                    resolution,
                    manifest_hash,
                )

    for row in source_rows:
        builder.sources.append(_source_resolution_row(row, hashes=hashes, matches_by_hash=matches_by_hash))

    scenes = sorted({str(row.get("scene_id")) for row in source_rows if row.get("scene_id")})
    identities_id = f"{rollout_id}:source-identities"
    builder.node(
        DatasetTopologyNode(
            identities_id,
            f"ASE source identities ({len(scenes)} scenes/{len(source_rows)} rows)",
            "ASE identities",
            "provenance",
            "referenced" if source_rows else "absent",
            None,
            "ASE source identities",
        )
    )
    builder.edge(aggregate_id, identities_id, "records ASE identities", "lineage only" if source_rows else "missing")

    if selected_source_row_id is not None:
        selected = next(
            (row for row in source_rows if _as_int(row.get("source_row_id")) == selected_source_row_id),
            None,
        )
        if selected is not None:
            _add_selected_source(
                builder,
                aggregate_id=aggregate_id,
                row=selected,
                hashes=hashes,
                matches_by_hash=matches_by_hash,
                paths=paths,
            )


def _add_selected_source(
    builder: _TopologyBuilder,
    *,
    aggregate_id: str,
    row: dict[str, Any],
    hashes: list[str],
    matches_by_hash: dict[str, list[_VinStoreSnapshot]],
    paths: _TopologyPaths,
) -> None:
    source_row_id = _as_int(row.get("source_row_id"))
    source_id = f"{aggregate_id}:source:{source_row_id}"
    builder.node(
        DatasetTopologyNode(
            source_id,
            f"Selected source {source_row_id}",
            "rollout source row",
            "provenance",
            "materialized",
            None,
            "Selected rollout source",
            dict(row),
        )
    )
    builder.edge(aggregate_id, source_id, "selects source row", "embedded", str(source_row_id))

    manifest_matches = [match for manifest_hash in hashes for match in matches_by_hash.get(manifest_hash, [])]
    if len(manifest_matches) == 1:
        snapshot = manifest_matches[0]
        sample_matches = _matching_samples(row, snapshot.index_records)
        if len(sample_matches) == 1:
            sample = sample_matches[0]
            sample_id = f"{_vin_id(snapshot.store_dir)}:sample:{sample.sample_index}"
            builder.node(
                DatasetTopologyNode(
                    sample_id,
                    f"VIN sample {sample.sample_index}: {sample.sample_key}",
                    "VIN sample",
                    "provenance",
                    "materialized",
                    (snapshot.store_dir / "sample_index.jsonl").as_posix(),
                    "Selected VIN sample",
                    {
                        "scene_id": sample.scene_id,
                        "snippet_id": sample.snippet_id,
                        "split": sample.split,
                        "shard_id": sample.shard_id,
                        "shard_row": sample.row,
                    },
                )
            )
            builder.edge(source_id, sample_id, "resolves source sample", "resolved pointer", sample.sample_key)
            _add_selected_shard(builder, snapshot=snapshot, sample=sample, sample_id=sample_id)
        else:
            unresolved_id = f"{source_id}:unresolved-sample"
            builder.node(
                DatasetTopologyNode(
                    unresolved_id,
                    "Unresolved VIN sample",
                    "unresolved pointer",
                    "provenance",
                    "absent",
                )
            )
            builder.edge(
                source_id,
                unresolved_id,
                "resolves source sample",
                "ambiguous" if sample_matches else "missing",
                f"matches={len(sample_matches)}",
            )

    scene = str(row.get("scene_id") or "unknown")
    snippet = str(row.get("snippet_id") or row.get("source_sample_key") or "unknown")
    scene_id = f"ase-scene:{scene}"
    snippet_id = f"ase-snippet:{scene}:{snippet}"
    builder.node(DatasetTopologyNode(scene_id, f"ASE scene {scene}", "ASE scene", "provenance", "referenced"))
    builder.node(
        DatasetTopologyNode(
            snippet_id,
            f"ATEK snippet {snippet}",
            "ATEK snippet identity",
            "actor-visible",
            "referenced",
        )
    )
    builder.edge(source_id, scene_id, "records scene identity", "lineage only", scene)
    builder.edge(source_id, snippet_id, "records snippet identity", "lineage only", snippet)
    _add_selected_meshes(builder, scene_id=scene_id, scene=scene, paths=paths)


def _add_selected_shard(
    builder: _TopologyBuilder,
    *,
    snapshot: _VinStoreSnapshot,
    sample: VinOfflineIndexRecord,
    sample_id: str,
) -> None:
    assert snapshot.manifest is not None
    shard = next((item for item in snapshot.manifest.shards if item.shard_id == sample.shard_id), None)
    if shard is None:
        return
    shard_path = snapshot.store_dir / shard.relative_dir
    shard_id = f"{_vin_id(snapshot.store_dir)}:shard:{shard.shard_id}"
    builder.node(
        DatasetTopologyNode(
            shard_id,
            f"{shard.shard_id} row {sample.row}",
            "VIN shard row",
            "provenance",
            _path_availability(shard_path),
            shard_path.as_posix(),
            "Selected VIN shard",
        )
    )
    builder.edge(sample_id, shard_id, "stored in shard row", _embedded_or_missing(shard_path), str(sample.row))


def _add_selected_meshes(
    builder: _TopologyBuilder,
    *,
    scene_id: str,
    scene: str,
    paths: _TopologyPaths,
) -> None:
    gt_path = paths.resolve_mesh_path(scene)
    gt_id = f"mesh:gt:{scene}"
    builder.node(
        DatasetTopologyNode(
            gt_id,
            f"GT mesh {scene}",
            "GT mesh",
            "oracle/evaluation",
            _path_availability(gt_path),
            gt_path.as_posix(),
            "GT scene mesh",
        )
    )
    builder.edge(
        scene_id,
        gt_id,
        "resolves GT mesh",
        "inferred path" if gt_path.exists() else "missing",
        "PathConfig.resolve_mesh_path",
    )

    processed_matches = sorted(paths.processed_meshes.glob(f"scene_{scene}_*.ply"))
    processed_id = f"mesh:processed:{scene}"
    if len(processed_matches) == 1:
        processed_path = processed_matches[0]
        resolution: TopologyResolution = "inferred path"
        availability: TopologyAvailability = "materialized"
    elif len(processed_matches) > 1:
        processed_path = paths.processed_meshes
        resolution = "ambiguous"
        availability = "referenced"
    else:
        processed_path = paths.processed_meshes / f"scene_{scene}_*.ply"
        resolution = "missing"
        availability = "absent"
    builder.node(
        DatasetTopologyNode(
            processed_id,
            f"Processed mesh {scene}",
            "processed mesh",
            "oracle/evaluation",
            availability,
            processed_path.as_posix(),
            "Processed scene mesh",
            {"match_count": len(processed_matches)},
        )
    )
    builder.edge(
        scene_id,
        processed_id,
        "resolves processed mesh",
        resolution,
        "PathConfig.processed_meshes + scene identity",
    )


def _source_resolution_row(
    row: dict[str, Any],
    *,
    hashes: list[str],
    matches_by_hash: dict[str, list[_VinStoreSnapshot]],
) -> dict[str, Any]:
    output = dict(row)
    manifest_matches = [match for manifest_hash in hashes for match in matches_by_hash.get(manifest_hash, [])]
    output["source_manifest_hashes"] = list(hashes)
    output["vin_store_matches"] = [match.store_dir.as_posix() for match in manifest_matches]
    output["vin_sample_index"] = None
    if len(manifest_matches) != 1:
        output["source_resolution"] = "ambiguous" if manifest_matches else "missing"
        return output
    sample_matches = _matching_samples(row, manifest_matches[0].index_records)
    if len(sample_matches) == 1:
        output["source_resolution"] = "resolved pointer"
        output["vin_sample_index"] = sample_matches[0].sample_index
    elif sample_matches:
        output["source_resolution"] = "ambiguous"
    else:
        output["source_resolution"] = "missing"
    return output


def _matching_samples(
    row: dict[str, Any],
    records: tuple[VinOfflineIndexRecord, ...],
) -> list[VinOfflineIndexRecord]:
    source_index = _as_int(row.get("source_sample_index"))
    if source_index is not None:
        indexed = [record for record in records if record.sample_index == source_index]
        if indexed and all(_sample_identity_matches(row, record) for record in indexed):
            return indexed
        if indexed:
            return []
    source_key = _canonical_sample_key(row.get("source_sample_key"))
    return [
        record
        for record in records
        if _canonical_sample_key(record.sample_key) == source_key and _sample_identity_matches(row, record)
    ]


def _sample_identity_matches(row: dict[str, Any], record: VinOfflineIndexRecord) -> bool:
    expected_pairs = (
        (row.get("scene_id"), record.scene_id),
        (row.get("snippet_id"), record.snippet_id),
        (row.get("split"), record.split),
        (row.get("source_shard_id"), record.shard_id),
        (row.get("source_shard_row"), record.row),
    )
    for expected, actual in expected_pairs:
        if expected is None:
            continue
        if "snippet" in str(expected).lower() or "atek" in str(expected).lower():
            if _canonical_sample_key(expected) != _canonical_sample_key(actual):
                return False
        elif str(expected) != str(actual):
            return False
    return True


def _canonical_sample_key(value: object) -> str:
    compact = compact_ase_atek_sample_id(str(value or ""))
    return compact.rsplit("::", maxsplit=1)[-1]


def _source_manifest_hashes(manifest: dict[str, Any]) -> list[str]:
    config_hashes = manifest.get("config_hashes")
    if not isinstance(config_hashes, dict):
        return []
    hashes = config_hashes.get("source_manifest")
    if not isinstance(hashes, list):
        return []
    return sorted({str(value) for value in hashes if value})


def _rollout_source_rows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    coverage = manifest.get("source_coverage")
    if not isinstance(coverage, dict) or not isinstance(coverage.get("sources"), list):
        return []
    rows = [dict(row) for row in coverage["sources"] if isinstance(row, dict)]
    return sorted(rows, key=lambda row: (_as_int(row.get("source_row_id")) is None, _as_int(row.get("source_row_id"))))


def _read_json_object(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object at {path}.")
    return payload


def _vin_id(path: Path) -> str:
    return f"vin:{path.resolve().as_posix()}"


def _block_role(name: str) -> TopologyRole:
    if name.startswith(("oracle.", "gt.")):
        return "oracle/evaluation"
    if name.startswith("vin."):
        return "derived training data"
    if name.startswith(("backbone.", "efm.", "trajectory.")):
        return "actor-visible"
    return "provenance"


def _path_availability(path: Path) -> TopologyAvailability:
    return "materialized" if path.exists() else "absent"


def _embedded_or_missing(path: Path) -> TopologyResolution:
    return "embedded" if path.exists() else "missing"


def _collection_availability(paths: list[Path]) -> TopologyAvailability:
    if paths and all(path.exists() for path in paths):
        return "materialized"
    if any(path.exists() for path in paths):
        return "referenced"
    return "absent"


def _collection_resolution(paths: list[Path]) -> TopologyResolution:
    if paths and all(path.exists() for path in paths):
        return "embedded"
    if any(path.exists() for path in paths):
        return "ambiguous"
    return "missing"


def _atek_root(
    manifest: VinOfflineManifest,
    paths: _TopologyPaths,
) -> tuple[Path, TopologyResolution]:
    dataset_config = manifest.source.get("dataset_config")
    if isinstance(dataset_config, dict):
        variant = str(dataset_config.get("atek_variant") or "efm")
        stored_paths = dataset_config.get("paths")
        if isinstance(stored_paths, dict) and stored_paths.get("data_root"):
            root = Path(str(stored_paths["data_root"])).expanduser().resolve() / f"ase_{variant}"
            return root, "resolved pointer" if root.exists() else "missing"
    inferred = paths.data_root / "ase_efm"
    return inferred, "inferred path" if inferred.exists() else "missing"


def _resolution_counts(edges: tuple[DatasetTopologyEdge, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        counts[edge.resolution] = counts.get(edge.resolution, 0) + 1
    return dict(sorted(counts.items()))


def _aggregate_graph(
    nodes: tuple[DatasetTopologyNode, ...],
    edges: tuple[DatasetTopologyEdge, ...],
) -> tuple[tuple[DatasetTopologyNode, ...], tuple[DatasetTopologyEdge, ...]]:
    """Collapse detailed VIN block nodes into one family per role and store."""

    block_nodes = {node.node_id: node for node in nodes if node.kind == "VIN block"}
    if not block_nodes:
        return nodes, edges

    replacements: dict[str, str] = {}
    grouped: dict[str, list[DatasetTopologyNode]] = {}
    for node_id, node in block_nodes.items():
        store_id = node_id.split(":block:", maxsplit=1)[0]
        group_id = f"{store_id}:block-family:{node.role}"
        replacements[node_id] = group_id
        grouped.setdefault(group_id, []).append(node)

    aggregate_nodes = [node for node in nodes if node.node_id not in block_nodes]
    for group_id, members in grouped.items():
        aggregate_nodes.append(
            DatasetTopologyNode(
                group_id,
                f"{members[0].role} VIN blocks ({len(members)})",
                "VIN block family",
                members[0].role,
                _aggregate_availability([member.availability for member in members]),
                members[0].path,
                f"VIN block family: {members[0].role}",
                {"block_names": sorted(member.label for member in members)},
            )
        )

    aggregate_edges: list[DatasetTopologyEdge] = []
    for edge in edges:
        source = replacements.get(edge.source, edge.source)
        target = replacements.get(edge.target, edge.target)
        if source == target:
            continue
        candidate = DatasetTopologyEdge(
            source,
            target,
            "materializes block family" if edge.target in block_nodes else edge.relation,
            edge.resolution,
            edge.evidence,
        )
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(aggregate_edges)
                if (existing.source, existing.target, existing.relation)
                == (candidate.source, candidate.target, candidate.relation)
            ),
            None,
        )
        if duplicate_index is None:
            aggregate_edges.append(candidate)
            continue
        existing = aggregate_edges[duplicate_index]
        aggregate_edges[duplicate_index] = DatasetTopologyEdge(
            existing.source,
            existing.target,
            existing.relation,
            _worst_resolution(existing.resolution, candidate.resolution),
            existing.evidence,
        )
    return tuple(aggregate_nodes), tuple(aggregate_edges)


def _aggregate_availability(values: list[TopologyAvailability]) -> TopologyAvailability:
    if all(value == "materialized" for value in values):
        return "materialized"
    if all(value == "absent" for value in values):
        return "absent"
    if any(value == "materialized" for value in values):
        return "referenced"
    return "optional"


def _worst_resolution(
    left: TopologyResolution,
    right: TopologyResolution,
) -> TopologyResolution:
    rank: dict[TopologyResolution, int] = {
        "embedded": 0,
        "resolved pointer": 1,
        "lineage only": 2,
        "inferred path": 3,
        "ambiguous": 4,
        "missing": 5,
    }
    return left if rank[left] >= rank[right] else right


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "DatasetTopology",
    "DatasetTopologyEdge",
    "DatasetTopologyNode",
    "TopologyAvailability",
    "TopologyResolution",
    "TopologyRole",
    "build_dataset_topology",
    "discover_vin_store_dirs",
]
