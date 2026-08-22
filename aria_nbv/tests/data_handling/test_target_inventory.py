from pathlib import Path
from types import SimpleNamespace

import numpy as np

from aria_nbv.data_handling.vin_store import target_inventory
from aria_nbv.data_handling.vin_store.format import VinOfflineIndexRecord, VinOfflineShardSpec


def _records() -> tuple[VinOfflineIndexRecord, ...]:
    return (
        VinOfflineIndexRecord(0, "sample-a", "scene-a", "snippet-a", "train", "shard-a", 0),
        VinOfflineIndexRecord(1, "sample-b", "scene-b", "snippet-b", "val", "shard-b", 0),
    )


def _manifest(*, detected: bool = True, gt: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        materialized_blocks=SimpleNamespace(detected_obbs=detected, gt_obbs=gt),
        shards=[
            VinOfflineShardSpec(
                "shard-a", "shards/a", 0, 1, {name: SimpleNamespace() for name in ("gt.obbs", "detected.obbs")}
            ),
            VinOfflineShardSpec(
                "shard-b", "shards/b", 1, 1, {name: SimpleNamespace() for name in ("gt.obbs", "detected.obbs")}
            ),
        ],
    )


def test_inventory_extracts_geometry_class_and_excludes_padding_and_nonfinite(monkeypatch, tmp_path: Path) -> None:
    valid = np.zeros((34,), dtype=np.float32)
    valid[:6] = [0, 2, 0, 1, 0, 3]
    valid[30:33] = [7, 11, 0.8]
    padded = np.full((34,), -1, dtype=np.float32)
    nonfinite = valid.copy()
    nonfinite[0] = np.nan

    class Reader:
        def __init__(self, _config: object) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, name: str) -> np.ndarray:
            return np.stack([valid, padded, nonfinite]) if record.sample_index == 0 else valid.reshape(1, 34)

        def read_optional_record(self, _record: VinOfflineIndexRecord, name: str) -> object:
            return {7: "chair"} if name.endswith("obb_sem_id_to_name") else None

    monkeypatch.setattr(target_inventory.VinOfflineManifest, "read", classmethod(lambda _cls, _path: _manifest()))
    monkeypatch.setattr(
        target_inventory.VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records()))
    )
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", Reader)

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.gt.available is True
    assert result.gt.row_count == 2
    assert result.gt.excluded_padding_count == 1
    assert result.gt.excluded_nonfinite_count == 1
    assert result.gt.class_counts == (("chair", 2),)
    assert result.gt.rows[0].center == (1.0, 0.5, 1.5)
    assert result.gt.rows[0].volume == 6.0
    assert result.gt.rows[0].aspect_ratio == 3.0
    assert result.to_jsonable()["detected"]["row_count"] == 2


def test_inventory_keeps_missing_population_explicitly_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        target_inventory.VinOfflineManifest,
        "read",
        classmethod(lambda _cls, _path: _manifest(gt=False, detected=False)),
    )
    monkeypatch.setattr(
        target_inventory.VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records()))
    )
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", lambda _config: object())

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.detected.available is False
    assert result.gt.available is False
    assert result.gt.rows == ()
    assert result.gt.reason == "gt.obbs_not_materialized"


def test_inventory_rejects_malformed_shape_without_fallback(monkeypatch, tmp_path: Path) -> None:
    class Reader:
        def __init__(self, _config: object) -> None:
            pass

        def read_numeric_block(self, _record: VinOfflineIndexRecord, _name: str) -> np.ndarray:
            return np.zeros((3, 33), dtype=np.float32)

    monkeypatch.setattr(target_inventory.VinOfflineManifest, "read", classmethod(lambda _cls, _path: _manifest()))
    monkeypatch.setattr(
        target_inventory.VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records()))
    )
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", Reader)

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.gt.available is False
    assert result.gt.reason == "gt.obbs_shape_invalid:[3, 33]"
    assert result.gt.rows == ()
