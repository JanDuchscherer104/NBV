"""Test-first regressions for the canonical VIN snippet-frame gauge."""

from __future__ import annotations

import json
from dataclasses import asdict, fields
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW

from aria_nbv.data_handling.ase_efm.views import EfmSnippetView
from aria_nbv.data_handling.vin_store.adapter import build_vin_snippet_view
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)
from aria_nbv.data_handling.vin_store.store import (
    OFFLINE_DATASET_VERSION,
    VinOfflineShardWriter,
    VinOfflineStoreConfig,
    VinOfflineStoreReader,
)
from aria_nbv.data_handling.vin_store.views import VinSnippetView
from aria_nbv.targets.selection import observed_target_descriptors


def _pose(x: float) -> PoseTW:
    """Return one identity world pose with a distinctive x translation."""

    return PoseTW.from_Rt(
        torch.eye(3, dtype=torch.float32).unsqueeze(0),
        torch.tensor([[x, 0.0, 0.0]], dtype=torch.float32),
    )


def _raw_efm(*, snippet_x: float, rig_x: float) -> EfmSnippetView:
    """Build a raw EFM view whose snippet and rig gauges intentionally differ."""

    return EfmSnippetView(
        efm={
            ARIA_SNIPPET_T_WORLD_SNIPPET: _pose(snippet_x),
            "aria3d/pose/t_world_rig": _pose(rig_x),
        },
        scene_id="scene",
        snippet_id="snippet",
    )


def _manifest(*, version: int, shard: VinOfflineShardSpec | None = None) -> VinOfflineManifest:
    """Build the smallest valid manifest for reader contract tests."""

    return VinOfflineManifest(
        version=version,
        created_at="2026-08-19T00:00:00Z",
        source={},
        oracle={},
        vin={},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=False,
            depths=False,
            candidate_pcs=False,
        ),
        shards=[] if shard is None else [shard],
    )


def _write_actor_store(
    tmp_path: Path, *, include_snippet_gauge: bool
) -> tuple[VinOfflineStoreConfig, VinOfflineIndexRecord]:
    """Write one minimal actor row, optionally omitting the canonical gauge."""

    config = VinOfflineStoreConfig(store_dir=tmp_path / "vin-offline")
    shard_dir = config.shards_dir / "shard-000000"
    shard_writer = VinOfflineShardWriter(shard_dir)
    block_arrays = {
        "vin.points_world": np.asarray([[1.0, 2.0, 3.0, 0.5]], dtype=np.float32),
        "vin.lengths": np.asarray([[1]], dtype=np.int64),
        "vin.t_world_rig": _pose(99.0).tensor().numpy(),
    }
    if include_snippet_gauge:
        block_arrays["vin.t_world_snippet"] = _pose(7.0).tensor().numpy()
    blocks = {name: shard_writer.write_numeric_block(name, values) for name, values in block_arrays.items()}
    shard = VinOfflineShardSpec(
        shard_id="shard-000000",
        relative_dir="shards/shard-000000",
        row_start=0,
        num_rows=1,
        blocks=blocks,
    )
    record = VinOfflineIndexRecord(
        sample_index=0,
        sample_key="sample",
        scene_id="scene",
        snippet_id="snippet",
        split="train",
        shard_id=shard.shard_id,
        row=0,
    )
    config.store_dir.mkdir(parents=True, exist_ok=True)
    _manifest(version=OFFLINE_DATASET_VERSION, shard=shard).write(config.manifest_path)
    config.sample_index_path.write_text(json.dumps(asdict(record)) + "\n", encoding="utf-8")
    return config, record


def test_vin_snippet_view_exposes_canonical_t_world_snippet_pose() -> None:
    """VIN DTOs carry the persisted world-from-snippet gauge as PoseTW[1,12]."""

    snippet = VinSnippetView(
        points_world=torch.zeros((1, 4), dtype=torch.float32),
        lengths=torch.ones((1,), dtype=torch.int64),
        t_world_rig=_pose(99.0),
        t_world_snippet=_pose(7.0),
    )

    assert tuple(snippet.t_world_snippet.tensor().shape) == (1, 12)
    torch.testing.assert_close(snippet.t_world_snippet.tensor(), _pose(7.0).tensor())


def test_public_vin_snippet_api_declares_canonical_gauge_field() -> None:
    """Public DTO and owner-leaf exports include the new canonical field."""

    from aria_nbv.data_handling import VinSnippetView as RootVinSnippetView
    from aria_nbv.data_handling.vin_store import views

    assert "t_world_snippet" in {field.name for field in fields(VinSnippetView)}
    assert RootVinSnippetView is views.VinSnippetView
    assert "VinSnippetView" in views.__all__


def test_raw_efm_snippet_gauge_is_preserved_by_vin_adapter() -> None:
    """Adapter output retains raw EFM t_world_snippet instead of rig history."""

    view = build_vin_snippet_view(
        _raw_efm(snippet_x=7.0, rig_x=99.0),
        device=torch.device("cpu"),
        max_points=None,
    )

    torch.testing.assert_close(view.t_world_snippet.tensor(), _pose(7.0).tensor())


def test_store_reader_roundtrip_preserves_canonical_snippet_gauge_exactly(tmp_path: Path) -> None:
    """VIN writer/store reader roundtrip keeps t_world_snippet byte-for-byte."""

    config, record = _write_actor_store(tmp_path, include_snippet_gauge=True)
    view = VinOfflineStoreReader(config).read_actor_snippet(record)

    torch.testing.assert_close(view.t_world_snippet.tensor(), _pose(7.0).tensor())


def test_reader_rejects_version_7_store_with_rebuild_guidance(tmp_path: Path) -> None:
    """Version-7 stores are rejected after the snippet-gauge format bump."""

    config = VinOfflineStoreConfig(store_dir=tmp_path / "vin-offline")
    config.store_dir.mkdir(parents=True)
    _manifest(version=7).write(config.manifest_path)
    config.sample_index_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match=r"Unsupported VIN offline dataset version.*Rebuild"):
        VinOfflineStoreReader(config)


def test_reader_rejects_store_missing_snippet_gauge_with_rebuild_guidance(tmp_path: Path) -> None:
    """Stores missing the canonical actor block fail closed with rebuild guidance."""

    config, record = _write_actor_store(tmp_path, include_snippet_gauge=False)

    with pytest.raises(ValueError, match=r"vin\.t_world_snippet.*Rebuild"):
        VinOfflineStoreReader(config).read_actor_snippet(record)


def test_observed_target_normalization_uses_persisted_snippet_gauge_not_rig_zero() -> None:
    """Observed target world coordinates use t_world_snippet, never t_world_rig[0]."""

    obb = ObbTW.from_lmc(
        bb3_object=torch.tensor([[-0.5, 0.5, -0.5, 0.5, -0.5, 0.5]]),
        bb2_rgb=torch.full((1, 4), -1.0),
        bb2_slaml=torch.full((1, 4), -1.0),
        bb2_slamr=torch.full((1, 4), -1.0),
        T_world_object=_pose(2.0),
        sem_id=torch.tensor([1]),
        inst_id=torch.tensor([2]),
        prob=torch.tensor([0.9]),
    )
    snippet = VinSnippetView(
        points_world=torch.zeros((0, 4)),
        lengths=torch.zeros((1,), dtype=torch.int64),
        t_world_rig=_pose(99.0),
        t_world_snippet=_pose(7.0),
    )
    sample = SimpleNamespace(
        sample_key="sample",
        vin_snippet=snippet,
        efm_snippet_view=None,
        detected_obbs=SimpleNamespace(obbs=obb.tensor(), sem_id_to_name={1: "chair"}),
        oracle=SimpleNamespace(reference_pose_world_rig=_pose(7.0)),
    )

    observed = observed_target_descriptors(sample)[0]

    assert observed.descriptor is not None
    assert observed.descriptor.center_world == pytest.approx((9.0, 0.0, 0.0))


def test_raw_efm_and_rebuilt_vin_store_produce_same_world_descriptor() -> None:
    """Raw EFM and rebuilt VIN representations yield one world-frame descriptor."""

    obb = ObbTW.from_lmc(
        bb3_object=torch.tensor([[-0.5, 0.5, -0.5, 0.5, -0.5, 0.5]]),
        bb2_rgb=torch.full((1, 4), -1.0),
        bb2_slaml=torch.full((1, 4), -1.0),
        bb2_slamr=torch.full((1, 4), -1.0),
        T_world_object=_pose(2.0),
        sem_id=torch.tensor([1]),
        inst_id=torch.tensor([2]),
        prob=torch.tensor([0.9]),
    )
    raw = _raw_efm(snippet_x=7.0, rig_x=99.0)
    rebuilt = VinSnippetView(
        points_world=torch.zeros((0, 4)),
        lengths=torch.zeros((1,), dtype=torch.int64),
        t_world_rig=_pose(99.0),
        t_world_snippet=_pose(7.0),
    )

    def sample(snippet: object) -> SimpleNamespace:
        return SimpleNamespace(
            sample_key="sample",
            vin_snippet=rebuilt,
            efm_snippet_view=snippet if isinstance(snippet, EfmSnippetView) else None,
            detected_obbs=SimpleNamespace(obbs=obb.tensor(), sem_id_to_name={1: "chair"}),
            oracle=SimpleNamespace(reference_pose_world_rig=_pose(7.0)),
        )

    raw_descriptor = observed_target_descriptors(sample(raw))[0].descriptor
    rebuilt_descriptor = observed_target_descriptors(sample(rebuilt))[0].descriptor

    assert raw_descriptor == rebuilt_descriptor
