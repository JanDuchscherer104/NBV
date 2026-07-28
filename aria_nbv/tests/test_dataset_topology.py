from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import zarr

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from aria_nbv.dataset_topology import (
    NativeDatasetLayout,
    TopologyNode,
    TopologyRelationship,
    TopologySnapshot,
    build_dataset_topology,
    build_native_dataset_layout,
    discover_vin_store_dirs,
)
from aria_nbv.utils.fingerprints import stable_msgspec_hash


def _write_vin_store(root: Path, *, name: str = "vin") -> tuple[Path, str]:
    store = root / name
    shard_dir = store / "shards" / "shard-000000"
    shard_dir.mkdir(parents=True)
    block = VinOfflineBlockSpec.for_zarr_array(
        name="oracle.rri",
        array_path="oracle/rri",
        dtype="float32",
        shape=[1, 2],
    )
    (shard_dir / "oracle" / "rri").mkdir(parents=True)
    manifest = VinOfflineManifest(
        version=7,
        created_at="2026-07-18T00:00:00Z",
        source={
            "dataset_config": {
                "atek_variant": "efm",
                "paths": {"data_root": (root / "atek-data").as_posix()},
            }
        },
        oracle={},
        vin={},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=False,
            depths=False,
            candidate_pcs=False,
            gt_obbs=False,
            detected_obbs=False,
            trajectory=False,
        ),
        stats={"num_samples": 1, "num_train": 1, "num_val": 0},
        provenance={},
        shards=[
            VinOfflineShardSpec(
                shard_id="shard-000000",
                relative_dir="shards/shard-000000",
                row_start=0,
                num_rows=1,
                blocks={block.name: block},
            )
        ],
    )
    manifest.write(store / "manifest.json")
    VinOfflineIndexRecord.write_many(
        store / "sample_index.jsonl",
        [
            VinOfflineIndexRecord(
                sample_index=0,
                sample_key="ASE_81286_Atek_000000",
                scene_id="81286",
                snippet_id="ASE_81286_Atek_000000",
                split="train",
                shard_id="shard-000000",
                row=0,
            )
        ],
    )
    splits = store / "splits"
    splits.mkdir()
    np.save(splits / "train.npy", np.asarray([0], dtype=np.int64))
    return store, stable_msgspec_hash(manifest)


def _write_rollout_store(root: Path, *, source_hash: str) -> Path:
    store = root / "rollouts.zarr"
    store.mkdir()
    for group in ("sources", "rollouts", "steps", "candidates", "selected_depth", "q_h"):
        group_dir = store / group
        group_dir.mkdir()
        (group_dir / "zarr.json").write_text("{}", encoding="utf-8")
    payload = {
        "manifest_version": "rollout-store-manifest-v1",
        "schema_id": "aria_nbv.rollout_zarr_q_invalidity",
        "schema_version": "1.0-target-rollout-core",
        "root_attrs": {
            "target_eval_crops_enabled": False,
            "target_eval_crops_num_rows": 0,
            "num_selected_depths": 1,
        },
        "counts": {"sources": 1, "selected_depths": 1, "target_eval_crops": 0},
        "config_hashes": {"source_manifest": [source_hash]},
        "source_coverage": {
            "num_source_rows": 1,
            "scene_counts": {"81286": 1},
            "split_counts": {"train": 1},
            "source_shard_counts": {"shard-000000": 1},
            "sources": [
                {
                    "source_row_id": 0,
                    "source_sample_index": 0,
                    "source_sample_key": "81286::ASE_81286_Atek_000000",
                    "scene_id": "81286",
                    "snippet_id": "ASE_81286_Atek_000000",
                    "split": "train",
                    "source_shard_id": "shard-000000",
                    "source_shard_row": 0,
                }
            ],
        },
    }
    (store / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return store


def _path_config(root: Path) -> PathConfig:
    return PathConfig(
        root=root,
        data_root=root / "data",
        offline_cache_dir=root / "offline",
        ase_meshes=root / "meshes",
        processed_meshes=root / "processed-meshes",
    )


def test_topology_resolves_rollout_lineage_by_exact_vin_manifest_hash(tmp_path: Path) -> None:
    vin_store, manifest_hash = _write_vin_store(tmp_path)
    rollout_store = _write_rollout_store(tmp_path, source_hash=manifest_hash)
    paths = _path_config(tmp_path)
    paths.resolve_mesh_path("81286").write_text("mesh", encoding="utf-8")

    topology = build_dataset_topology(
        rollout_store_dir=rollout_store,
        vin_store_dirs=[vin_store],
        path_config=paths,
        selected_source_row_id=0,
    )

    assert isinstance(topology, TopologySnapshot)
    assert all(isinstance(node, TopologyNode) for node in topology.nodes)
    assert all(isinstance(edge, TopologyRelationship) for edge in topology.edges)

    lineage_edges = [row for row in topology.edge_rows() if row["relation"] == "resolves manifest hash"]
    assert lineage_edges == [
        {
            "source": f"lineage:{manifest_hash}",
            "target": f"vin:{vin_store.resolve().as_posix()}",
            "relation": "resolves manifest hash",
            "resolution": "resolved pointer",
            "evidence": manifest_hash,
        }
    ]
    assert topology.source_rows()[0]["source_resolution"] == "resolved pointer"
    assert topology.source_rows()[0]["vin_sample_index"] == 0
    assert any(
        row["relation"] == "resolves GT mesh" and row["resolution"] == "inferred path" for row in topology.edge_rows()
    )


def test_topology_reports_ambiguous_and_missing_manifest_links_honestly(tmp_path: Path) -> None:
    vin_store, manifest_hash = _write_vin_store(tmp_path, name="vin-a")
    duplicate = tmp_path / "vin-b"
    duplicate.mkdir()
    (duplicate / "manifest.json").write_bytes((vin_store / "manifest.json").read_bytes())
    (duplicate / "sample_index.jsonl").write_bytes((vin_store / "sample_index.jsonl").read_bytes())
    rollout_store = _write_rollout_store(tmp_path, source_hash=manifest_hash)

    ambiguous = build_dataset_topology(
        rollout_store_dir=rollout_store,
        vin_store_dirs=[vin_store, duplicate],
        path_config=_path_config(tmp_path),
    )
    assert {row["resolution"] for row in ambiguous.edge_rows() if row["relation"] == "resolves manifest hash"} == {
        "ambiguous"
    }

    missing = build_dataset_topology(
        rollout_store_dir=rollout_store,
        vin_store_dirs=[],
        path_config=_path_config(tmp_path),
    )
    missing_edges = [row for row in missing.edge_rows() if row["relation"] == "resolves manifest hash"]
    assert len(missing_edges) == 1
    assert missing_edges[0]["resolution"] == "missing"
    assert missing_edges[0]["target"] == f"missing:vin:{manifest_hash}"


def test_topology_projects_modalities_sankey_json_and_rich_tree(tmp_path: Path) -> None:
    vin_store, manifest_hash = _write_vin_store(tmp_path)
    rollout_store = _write_rollout_store(tmp_path, source_hash=manifest_hash)
    report = tmp_path / "pilot-evidence.json"
    report.write_text("{}", encoding="utf-8")
    rerun = tmp_path / "inspection.rrd"

    topology = build_dataset_topology(
        rollout_store_dir=rollout_store,
        vin_store_dirs=[vin_store],
        path_config=_path_config(tmp_path),
        selected_source_row_id=0,
        report_bundle_paths=[report],
        rerun_recording_paths=[rerun],
    )

    modality_rows = topology.modality_rows()
    q_h = next(row for row in modality_rows if row["modality"] == "Derived Q_H cache")
    assert q_h["role"] == "derived training data"
    assert q_h["availability"] == "materialized"
    selected_depth = next(row for row in modality_rows if row["modality"] == "Selected depth")
    assert selected_depth["role"] == "oracle/evaluation"
    report_row = next(row for row in modality_rows if row["modality"] == "Evidence bundle")
    assert report_row["availability"] == "materialized"
    rerun_row = next(row for row in modality_rows if row["modality"] == "Rerun recording")
    assert rerun_row["availability"] == "absent"

    sankey = topology.sankey_data()
    assert set(sankey) == {"node", "link"}
    assert len(sankey["node"]["label"]) <= len(topology.node_rows())
    assert any("VIN blocks" in label for label in sankey["node"]["label"])
    assert max(sankey["link"]["source"] + sankey["link"]["target"]) < len(sankey["node"]["label"])
    assert topology.to_jsonable() == topology.to_jsonable()
    json.dumps(topology.to_jsonable(), sort_keys=True)
    tree = topology.plain_text_tree()
    assert "Dataset topology" in tree
    assert "rollouts.zarr" in tree
    assert "Selected source 0" in tree


def test_discover_vin_stores_requires_manifest_and_sample_index(tmp_path: Path) -> None:
    valid, _manifest_hash = _write_vin_store(tmp_path, name="valid")
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "manifest.json").write_text("{}", encoding="utf-8")

    assert discover_vin_store_dirs(tmp_path) == [valid.resolve()]


def test_stale_vin_manifest_retains_store_identity_without_claims(tmp_path: Path) -> None:
    stale = tmp_path / "stale-vin"
    stale.mkdir()
    (stale / "manifest.json").write_text('{"version": 1}', encoding="utf-8")
    (stale / "sample_index.jsonl").write_text("", encoding="utf-8")

    topology = build_dataset_topology(vin_store_dirs=[stale])

    assert len(topology.node_rows()) == 1
    node = topology.node_rows()[0]
    assert node["node_id"] == f"vin:{stale.resolve().as_posix()}"
    assert node["label"] == "VIN manifest: stale-vin"
    assert node["availability"] == "absent"
    assert node["details"]["error"]
    assert node["details"]["manifest_hash"] is None
    assert topology.edge_rows() == []


def _write_native_layout_stores(root: Path) -> tuple[Path, Path]:
    vin_store, manifest_hash = _write_vin_store(root, name="native-vin")
    shard_dir = vin_store / "shards" / "shard-000000"
    shutil.rmtree(shard_dir)
    shard = zarr.open_group(store=zarr.storage.LocalStore(str(shard_dir)), mode="w")
    shard.create_array(
        "vin/features",
        data=np.arange(12, dtype=np.float32).reshape(3, 4),
        chunks=(2, 4),
    )
    shard.create_array(
        "oracle/rri",
        data=np.asarray([[0.25, 0.5]], dtype=np.float32),
        chunks=(1, 2),
    )

    rollout_store = root / "native-rollouts.zarr"
    rollout = zarr.open_group(store=zarr.storage.LocalStore(str(rollout_store)), mode="w")
    arrays = {
        "sources/source_row_id": np.asarray([0], dtype=np.int64),
        "targets/target_row_id": np.asarray([0], dtype=np.int64),
        "rollouts/source_row_id": np.asarray([0], dtype=np.int64),
        "rollouts/target_row_id": np.asarray([0], dtype=np.int64),
        "rollouts/rollout_row_id": np.asarray([0], dtype=np.int64),
        "lineage/rollout_row_id": np.asarray([0], dtype=np.int64),
        "steps/rollout_row_id": np.asarray([0], dtype=np.int64),
        "steps/step_row_id": np.asarray([0], dtype=np.int64),
        "candidates/step_row_id": np.asarray([0], dtype=np.int64),
        "candidates/candidate_row_id": np.asarray([0], dtype=np.int64),
        "selected_depth/candidate_row_id": np.asarray([0], dtype=np.int64),
        "q_h/state_step_row_id": np.asarray([0], dtype=np.int64),
        "q_h/candidate_row_id": np.asarray([0], dtype=np.int64),
    }
    for path, data in arrays.items():
        rollout.create_array(path, data=data, chunks=data.shape)
    (rollout_store / "manifest.json").write_text(
        json.dumps({"config_hashes": {"source_manifest": [manifest_hash]}}),
        encoding="utf-8",
    )
    return vin_store, rollout_store


def test_native_layout_catalogs_shapes_chunks_and_declared_references(tmp_path: Path) -> None:
    vin_store, rollout_store = _write_native_layout_stores(tmp_path)

    layout = build_native_dataset_layout(
        root_store_dir=vin_store,
        rollout_store_dirs=[rollout_store],
    )

    assert isinstance(layout, NativeDatasetLayout)
    assert isinstance(layout, TopologySnapshot)
    assert all(isinstance(node, TopologyNode) for node in layout.nodes)
    assert all(isinstance(edge, TopologyRelationship) for edge in layout.edges)
    features = next(node for node in layout.nodes if node.details.get("relative_path") == "vin/features")
    assert features.details == {
        "relative_path": "vin/features",
        "dtype": "float32",
        "shape": [3, 4],
        "chunks": [2, 4],
    }
    assert features.role == "actor-visible"
    assert any(
        node.details.get("relative_path") == "oracle/rri" and node.role == "oracle/evaluation" for node in layout.nodes
    )
    assert any(edge.relation == "VIN manifest lineage" and edge.status == "resolved" for edge in layout.edges)
    assert any(edge.relation == "source row" for edge in layout.edges)
    assert any(edge.relation == "derived Q_H actions" for edge in layout.edges)
    assert "dtype=float32 shape=[3, 4] chunks=[2, 4]" in layout.tree_text()
    assert "digraph native_layout" in layout.graphviz_dot()


def test_native_layout_reports_missing_metadata_without_inventing_arrays(tmp_path: Path) -> None:
    missing_vin = tmp_path / "missing-vin"
    missing_rollout = tmp_path / "missing-rollout.zarr"

    layout = build_native_dataset_layout(
        root_store_dir=missing_vin,
        rollout_store_dirs=[missing_rollout],
    )

    assert not any(node.kind == "array" for node in layout.nodes)
    assert any(node.kind == "error" and "unreadable" in layout.tree_text() for node in layout.nodes)
    assert any(edge.status == "missing" for edge in layout.edges)
    lineage = next(edge for edge in layout.edges if edge.relation == "VIN manifest lineage")
    assert lineage.status == "blocked"
