"""Tests for typed ASE dataset wrapper (updated to new AseEfmDataset API)."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("efm3d")

import torch
import trimesh
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from torch.utils.data import DataLoader

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.ase_efm.dataset import AseEfmDataset, AseEfmDatasetConfig
from aria_nbv.data_handling.ase_efm.views import EfmCameraView, EfmSnippetView
from aria_nbv.data_handling.identifiers import compact_ase_atek_sample_id, raw_ase_atek_sample_id


def _paths(tmp_path: Path) -> PathConfig:
    """Create an isolated PathConfig rooted at tmp_path."""

    data_root = (tmp_path / "data_root").resolve()
    url_dir = (tmp_path / "urls").resolve()
    ase_meshes = (tmp_path / "meshes").resolve()
    processed_meshes = (tmp_path / "meshes_processed").resolve()
    for p in (data_root, url_dir, ase_meshes, processed_meshes):
        p.mkdir(parents=True, exist_ok=True)
    return PathConfig(
        root=PathConfig().root,  # keep project root for external/
        data_root=data_root,
        url_dir=url_dir,
        ase_meshes=ase_meshes,
        processed_meshes=processed_meshes,
    )


def _identity_pose(batch: int = 2) -> PoseTW:
    return PoseTW(torch.tensor([[1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]]).repeat(batch, 1))


def _mock_efm_sample(scene: str = "00000", snippet: str = "shards-0000") -> dict:
    """Construct a minimal EFM-formatted sample accepted by AseEfmDataset."""

    cam = CameraTW(torch.randn(2, 34))
    return {
        "sequence_name": scene,
        "__url__": f"/tmp/{scene}/{snippet}.tar",
        "rgb/img": torch.randn(2, 3, 4, 4),
        "rgb/calib": cam,
        "rgb/img/time_ns": torch.tensor([0, 1], dtype=torch.int64),
        "rgb/frame_id_in_sequence": torch.tensor([0, 1], dtype=torch.int64),
        "pose/t_world_rig": _identity_pose(),
        "pose/time_ns": torch.tensor([0, 1], dtype=torch.int64),
        "pose/gravity_in_world": torch.tensor([0.0, 0.0, -9.81]),
        "points/p3s_world": torch.zeros(2, 5, 3),
        "points/dist_std": torch.ones(2, 5),
        "points/inv_dist_std": torch.ones(2, 5),
        "points/time_ns": torch.tensor([0, 1], dtype=torch.int64),
        "scene/points/vol_min": torch.tensor([0.0, 0.0, 0.0]),
        "scene/points/vol_max": torch.tensor([1.0, 1.0, 1.0]),
        "points/lengths": torch.tensor([5, 5], dtype=torch.int64),
        "gt_data": {},
    }


def _collate(samples: list[EfmSnippetView]) -> dict:
    return {
        "scene_id": [s.scene_id for s in samples],
        "samples": samples,
        "mesh": [s.mesh for s in samples],
    }


class TestAseEfmDatasetConfig:
    def test_accepts_manual_tar_urls(self, tmp_path: Path):
        paths = _paths(tmp_path)
        scene = "00000"
        tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
        tar.parent.mkdir(parents=True, exist_ok=True)
        tar.write_bytes(b"dummy")
        cfg = AseEfmDatasetConfig(
            paths=paths,
            scene_ids=[scene],
            load_meshes=False,
            mesh_crop_margin_m=None,
            verbosity=0,
        )
        assert cfg.scene_ids == [scene]


class TestAseEfmDataset:
    @pytest.fixture
    def dataset(self, tmp_path: Path) -> Generator[AseEfmDataset, None, None]:
        paths = _paths(tmp_path)
        efm_sample = _mock_efm_sample()
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm_sample])
        mock_loader.__len__.return_value = 1

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            scene = "00000"
            tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[scene],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            yield AseEfmDataset(config)

    def test_iter_yields_efm_snippet_view(self, dataset: AseEfmDataset):
        sample = next(iter(dataset))
        assert isinstance(sample, EfmSnippetView)
        assert sample.scene_id == "00000"
        assert sample.snippet_id == "shards-0000"
        cam = sample.camera_rgb
        traj = sample.trajectory
        assert cam.images.shape == (2, 3, 4, 4)
        assert traj.t_world_rig.matrix3x4.shape == (2, 3, 4)

    def test_compacts_ase_atek_key_identifiers(self, tmp_path: Path):
        paths = _paths(tmp_path)
        efm = _mock_efm_sample(scene="81286", snippet="shards-0000")
        efm["__key__"] = "AriaSyntheticEnvironment_81286_AtekDataSample_000000"
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm])
        mock_loader.__len__.return_value = 1

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            tar = paths.resolve_atek_data_dir("efm") / "81286" / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=["81286"],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            sample = next(iter(AseEfmDataset(config)))

        assert sample.scene_id == "81286"
        assert sample.snippet_id == "ASE_81286_Atek_000000"

    def test_dataloader_collation(self, tmp_path: Path):
        paths = _paths(tmp_path)
        efm1 = _mock_efm_sample(scene="00000", snippet="shards-0000")
        efm2 = _mock_efm_sample(scene="00001", snippet="shards-0001")
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm1, efm2])
        mock_loader.__len__.return_value = 2

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            for scene in ("00000", "00001"):
                tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
                tar.parent.mkdir(parents=True, exist_ok=True)
                tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=["00000", "00001"],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            dataset = AseEfmDataset(config)
            loader = DataLoader(dataset, batch_size=2, collate_fn=_collate)
            batch = next(iter(loader))

        assert batch["scene_id"] == ["00000", "00001"]
        assert len(batch["samples"]) == 2

    def test_from_cache_efm_parses_key_and_bounds(self):
        efm = _mock_efm_sample(scene="82832", snippet="shards-0007")
        efm["__key__"] = "AriaSyntheticEnvironment_82832_AtekDataSample_000056"
        sample = EfmSnippetView.from_cache_efm(efm)
        assert sample.scene_id == "82832"
        assert sample.snippet_id == "ASE_82832_Atek_000056"
        assert sample.crop_bounds is not None
        bounds_min, bounds_max = sample.crop_bounds
        assert torch.allclose(bounds_min, torch.tensor([0.0, 0.0, 0.0]))
        assert torch.allclose(bounds_max, torch.tensor([1.0, 1.0, 1.0]))

    def test_missing_camera_key_raises(self, tmp_path: Path):
        efm = _mock_efm_sample()
        efm.pop("rgb/img")
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm])
        mock_loader.__len__.return_value = 1

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            paths = _paths(tmp_path)
            scene = "00000"
            tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[scene],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            dataset = AseEfmDataset(config)
            sample = next(iter(dataset))

        with pytest.raises(KeyError):
            _ = sample.camera_rgb

    def test_repr_is_multiline_and_summarized(self, tmp_path: Path):
        efm = _mock_efm_sample()
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm])
        mock_loader.__len__.return_value = 1

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            paths = _paths(tmp_path)
            scene = "00000"
            tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[scene],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            sample = next(iter(AseEfmDataset(config)))

        rep = repr(sample)
        assert "scene" in rep and "cameras" in rep
        assert "\n" in rep

    def test_camera_docstring_has_shapes(self):
        doc = EfmCameraView.__doc__
        assert doc is not None
        assert "camera stream view" in doc.lower()

    def test_to_moves_tensors(self, tmp_path: Path):
        efm = _mock_efm_sample()
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm])
        mock_loader.__len__.return_value = 1

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            paths = _paths(tmp_path)
            scene = "00000"
            tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[scene],
                scene_to_mesh={},
                load_meshes=False,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            sample = next(iter(AseEfmDataset(config)))

        cam = sample.camera_rgb
        moved = cam.to("cpu")
        assert moved.images.device.type == "cpu"

    def test_mesh_loading_and_caching(self, tmp_path: Path):
        scene_id = "00000"
        mesh_path = tmp_path / "scene_ply_00000.ply"
        trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]]).export(mesh_path)

        efm = _mock_efm_sample(scene=scene_id)
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter([efm, efm])
        mock_loader.__len__.return_value = 2

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            paths = _paths(tmp_path)
            tar = paths.resolve_atek_data_dir("efm") / scene_id / "dummy.tar"
            tar.parent.mkdir(parents=True, exist_ok=True)
            tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[scene_id],
                scene_to_mesh={scene_id: mesh_path},
                load_meshes=True,
                cache_meshes=True,
                crop_mesh=False,
                mesh_simplify_ratio=None,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            dataset = AseEfmDataset(config)
            samples = list(dataset)

        assert samples[0].mesh is not None
        assert samples[1].mesh is not None
        assert samples[0].mesh.faces.shape == samples[1].mesh.faces.shape
        assert samples[0].mesh.vertices.shape == samples[1].mesh.vertices.shape

    def test_mesh_cache_can_be_disabled_for_unique_scene_iteration(self, tmp_path: Path):
        mesh_path = tmp_path / "scene.ply"
        trimesh.Trimesh(vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]]).export(mesh_path)
        efm_samples = [_mock_efm_sample(scene="00000"), _mock_efm_sample(scene="00001")]
        mock_loader = MagicMock()
        mock_loader.__iter__.return_value = iter(efm_samples)
        mock_loader.__len__.return_value = len(efm_samples)

        with patch.object(AseEfmDataset, "_load_atek_wds_dataset_as_efm", return_value=mock_loader):
            paths = _paths(tmp_path)
            for scene in ("00000", "00001"):
                tar = paths.resolve_atek_data_dir("efm") / scene / "dummy.tar"
                tar.parent.mkdir(parents=True, exist_ok=True)
                tar.write_bytes(b"dummy")
            config = AseEfmDatasetConfig(
                paths=paths,
                scene_ids=["00000", "00001"],
                scene_to_mesh={"00000": mesh_path, "00001": mesh_path},
                load_meshes=True,
                cache_meshes=False,
                crop_mesh=False,
                mesh_simplify_ratio=None,
                batch_size=None,
                mesh_crop_margin_m=None,
                verbosity=0,
            )
            dataset = AseEfmDataset(config)
            samples = list(dataset)

        assert all(sample.mesh is not None for sample in samples)
        assert dataset._mesh_cache == {}


def test_ase_atek_identifier_conversion_round_trip() -> None:
    raw = "AriaSyntheticEnvironment_81286_AtekDataSample_000000"
    compact = "ASE_81286_Atek_000000"

    assert compact_ase_atek_sample_id(raw) == compact
    assert raw_ase_atek_sample_id(compact) == raw
    assert compact_ase_atek_sample_id("snippet-000") == "snippet-000"
    assert raw_ase_atek_sample_id("snippet-000") is None


class TestGTViewRealData:
    def test_parses_efm_gt_obb3(self):
        tar = Path(".data/ase_efm_eval/81286/shards-0000.tar")
        if not tar.exists():
            pytest.skip("real ASE shard missing locally")

        config = AseEfmDatasetConfig(
            atek_variant="efm_eval",
            scene_ids=[tar.parent.name],
            scene_to_mesh={},
            load_meshes=False,
            batch_size=None,
            verbosity=0,
        )
        sample = next(iter(AseEfmDataset(config)))
        gt = sample.gt

        # Should at least produce a dict, even if empty.
        assert isinstance(gt.efm_gt, dict)
