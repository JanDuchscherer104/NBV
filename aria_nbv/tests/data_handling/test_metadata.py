"""Tests for metadata.py module."""

import json
from pathlib import Path

import pytest

from aria_nbv.data_handling.atek_downloads.metadata import ASEMetadata, SceneMetadata


class TestSceneMetadata:
    """Tests for SceneMetadata dataclass."""

    def test_creation(self):
        """Test creating SceneMetadata instance."""
        meta = SceneMetadata(
            scene_id="82832",
            has_gt_mesh=True,
            mesh_url="https://example.com/mesh.ply",
            mesh_sha="abc123",
            shard_count=3,
            shard_ids=["82832_seq_000", "82832_seq_001"],
            atek_config="efm",
            total_frames=200,
        )

        assert meta.scene_id == "82832"
        assert meta.has_gt_mesh is True
        assert meta.shard_count == 3
        assert len(meta.shard_ids) == 2

    def test_no_mesh(self):
        """Test SceneMetadata without GT mesh."""
        meta = SceneMetadata(
            scene_id="90000",
            has_gt_mesh=False,
            mesh_url=None,
            mesh_sha=None,
            shard_count=1,
            shard_ids=["90000_seq_000"],
            atek_config="efm",
            total_frames=100,
        )

        assert meta.has_gt_mesh is False
        assert meta.mesh_url is None
        assert meta.mesh_sha is None


class TestASEMetadata:
    """Tests for ASEMetadata class."""

    def test_initialization_empty_dir(self, tmp_url_dir: Path):
        """Test initialization with empty URL directory."""
        metadata = ASEMetadata(tmp_url_dir)

        assert metadata.url_dir == tmp_url_dir
        assert len(metadata.scenes) == 0
        assert len(metadata.mesh_scene_ids) == 0

    def test_parse_mesh_urls(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
    ):
        """Test parsing mesh download URLs."""
        metadata = ASEMetadata(tmp_url_dir)

        assert len(metadata.mesh_scene_ids) == 3
        assert "82832" in metadata.mesh_scene_ids
        assert "81022" in metadata.mesh_scene_ids
        assert "80001" in metadata.mesh_scene_ids

    def test_parse_atek_urls(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test parsing ATEK download URLs."""
        metadata = ASEMetadata(tmp_url_dir)

        # Check scene creation
        assert len(metadata.scenes) == 3  # 82832, 81022, 90000
        assert "82832" in metadata.scenes
        assert "81022" in metadata.scenes
        assert "90000" in metadata.scenes

        # Check scene with mesh
        scene_82832 = metadata.scenes["82832"]
        assert scene_82832.scene_id == "82832"
        assert scene_82832.has_gt_mesh is True
        assert scene_82832.shard_count == 3  # efm config has 3 shards
        assert len(scene_82832.shard_ids) == 3

        # Check scene without mesh
        scene_90000 = metadata.scenes["90000"]
        assert scene_90000.has_gt_mesh is False
        assert scene_90000.mesh_url is None

    def test_get_scenes_with_meshes(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test filtering scenes with GT meshes."""
        metadata = ASEMetadata(tmp_url_dir)
        scenes_with_meshes = metadata.get_scenes_with_meshes()

        assert len(scenes_with_meshes) == 2  # 82832, 81022
        scene_ids = {s.scene_id for s in scenes_with_meshes}
        assert scene_ids == {"82832", "81022"}

    def test_filter_scenes_by_snippets(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test filtering scenes by minimum snippet count."""
        metadata = ASEMetadata(tmp_url_dir)

        # Filter for scenes with ≥3 snippets
        filtered = metadata.filter_scenes(min_shards=3, require_mesh=False, config="efm")

        assert len(filtered) == 1
        assert filtered[0].scene_id == "82832"
        assert filtered[0].shard_count == 3

    def test_filter_scenes_require_mesh(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test filtering scenes requiring GT mesh."""
        metadata = ASEMetadata(tmp_url_dir)

        # Filter for scenes with meshes
        filtered = metadata.filter_scenes(min_shards=0, require_mesh=True, config="efm")

        assert len(filtered) == 2
        scene_ids = {s.scene_id for s in filtered}
        assert scene_ids == {"82832", "81022"}

    def test_filter_scenes_by_config(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test filtering scenes by ATEK config."""
        metadata = ASEMetadata(tmp_url_dir)

        # Filter for cubercnn config
        filtered = metadata.filter_scenes(min_shards=0, require_mesh=False, config="cubercnn")

        # Only scene 82832 has cubercnn config
        assert len(filtered) == 1
        assert filtered[0].scene_id == "82832"
        assert filtered[0].shard_count == 1  # cubercnn has 1 shard

    def test_save_and_load(
        self,
        tmp_url_dir: Path,
        tmp_path: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test saving and loading metadata cache."""
        # Create and save metadata
        metadata = ASEMetadata(tmp_url_dir)
        cache_path = tmp_path / "metadata_cache.json"
        metadata.save(cache_path)

        assert cache_path.exists()

        # Load from cache
        loaded_metadata = ASEMetadata.load(cache_path)

        assert len(loaded_metadata.scenes) == len(metadata.scenes)
        assert loaded_metadata.mesh_scene_ids == metadata.mesh_scene_ids
        assert "82832" in loaded_metadata.scenes

    def test_load_invalid_cache(self, tmp_path: Path):
        """Test loading from invalid cache file."""
        cache_path = tmp_path / "invalid.json"
        cache_path.write_text("invalid json content {{{")

        with pytest.raises(json.JSONDecodeError):
            ASEMetadata.load(cache_path)

    def test_nonexistent_url_dir(self, tmp_path: Path):
        """Test initialization with non-existent URL directory."""
        nonexistent = tmp_path / "does_not_exist"

        # Should not raise - creates empty metadata
        metadata = ASEMetadata(nonexistent)
        assert len(metadata.scenes) == 0

    def test_multiple_configs_same_scene(
        self,
        tmp_url_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test scene with multiple ATEK configs uses first found."""
        metadata = ASEMetadata(tmp_url_dir)

        # Scene 82832 has both efm and cubercnn configs
        # Should use efm (first in iteration order)
        scene = metadata.scenes["82832"]
        assert scene.atek_config == "efm"
        assert scene.shard_count == 3
