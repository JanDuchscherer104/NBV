"""Tests for downloader.py module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aria_nbv.data_handling.atek_downloads.downloader import ASEDownloader, ASEDownloaderConfig
from aria_nbv.utils import Console, Verbosity

pytest.skip("Downloader API deprecated for current aria_nbv; skipping.", allow_module_level=True)


class TestASEDownloaderConfig:
    """Tests for ASEDownloaderConfig."""

    def test_creation(self, tmp_url_dir: Path, tmp_output_dir: Path):
        """Test creating config instance."""
        config = ASEDownloaderConfig(
            mode="download",
            url_dir=tmp_url_dir,
            output_dir=tmp_output_dir,
            verbosity=Verbosity.NORMAL,
        )

        assert config.url_dir == tmp_url_dir
        assert config.output_dir == tmp_output_dir
        assert config.verbosity == Verbosity.NORMAL

    def test_path_resolution(self, tmp_path: Path):
        """Test automatic path resolution."""
        config = ASEDownloaderConfig(
            mode="download",
            url_dir=str(tmp_path / "urls"),
            output_dir=str(tmp_path / "output"),
        )

        # Paths should be resolved to absolute
        assert config.url_dir.is_absolute()
        assert config.output_dir.is_absolute()

    def test_setup_target(
        self,
        tmp_url_dir: Path,
        tmp_output_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test setup_target creates downloader."""
        config = ASEDownloaderConfig(
            mode="download",
            url_dir=tmp_url_dir,
            output_dir=tmp_output_dir,
        )

        downloader = config.setup_target()

        assert isinstance(downloader, ASEDownloader)
        assert downloader.config == config
        assert len(downloader.metadata.scenes) > 0
        Console.with_prefix("test_downloader").log("setup_target ok")

    def test_setup_target_missing_url_dir(self, tmp_path: Path, tmp_output_dir: Path):
        """Test setup_target with missing URL directory."""
        nonexistent = tmp_path / "does_not_exist"

        config = ASEDownloaderConfig(
            mode="download",
            url_dir=nonexistent,
            output_dir=tmp_output_dir,
        )

        with pytest.raises(FileNotFoundError, match="URL directory not found"):
            config.setup_target()


class TestASEDownloader:
    """Tests for ASEDownloader class."""

    @pytest.fixture
    def downloader(
        self,
        tmp_url_dir: Path,
        tmp_output_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ) -> ASEDownloader:
        """Create downloader instance for testing."""
        config = ASEDownloaderConfig(
            mode="download",
            url_dir=tmp_url_dir,
            output_dir=tmp_output_dir,
            verbosity=Verbosity.QUIET,
        )
        return config.setup_target()

    def test_initialization(self, downloader: ASEDownloader):
        """Test downloader initialization."""
        assert downloader.metadata is not None
        assert len(downloader.metadata.scenes) > 0
        assert downloader.mesh_dir.exists()

    @patch("aria_nbv.data_handling.atek_downloads.downloader.requests.get")
    def test_download_single_mesh(
        self,
        mock_get: MagicMock,
        downloader: ASEDownloader,
        tmp_output_dir: Path,
    ):
        """Test downloading a single mesh file."""
        # Mock successful download
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_content = lambda chunk_size: [b"mock_mesh_data"]
        mock_get.return_value = mock_response

        # Create mock zip file
        import zipfile

        scene_id = "82832"
        zip_path = tmp_output_dir / "test.zip"

        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("scene_ply_82832.ply", "mock ply content")

        # Mock download to create zip
        with patch.object(
            downloader,
            "_download_file",
            return_value=zip_path,
        ):
            downloader.download_meshes([scene_id], overwrite=False)

            # Method ran without errors
            assert True

    def test_download_meshes_empty_list(self, downloader: ASEDownloader):
        """Test downloading with empty scene list."""
        # Should not raise
        downloader.download_meshes([], overwrite=False)

    def test_download_scenes_with_meshes(self, downloader: ASEDownloader):
        """Test download_scenes_with_meshes method."""
        with patch.object(downloader, "download_scenes") as mock_download:
            downloader.download_scenes_with_meshes(
                min_snippets=0,
                config="efm",
                overwrite=False,
            )

            # Should call download_scenes
            mock_download.assert_called_once()
            args = mock_download.call_args

            # Check scene_ids includes mesh scenes
            scene_ids = args[1]["scene_ids"]
            assert "82832" in scene_ids
            assert "81022" in scene_ids

    def test_download_scenes_filters_correctly(self, downloader: ASEDownloader):
        """Test download_scenes_with_meshes filters by snippet count."""
        with patch.object(downloader, "download_scenes") as mock_download:
            # Filter for ≥3 snippets
            downloader.download_scenes_with_meshes(
                min_snippets=3,
                config="efm",
                overwrite=False,
            )

            args = mock_download.call_args
            scene_ids = args[1]["scene_ids"]

            # Only 82832 has 3+ snippets
            assert scene_ids == ["82832"]

    def test_validate_sha_success(self, downloader: ASEDownloader, tmp_path: Path):
        """Test SHA validation with correct hash."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        # Calculate actual SHA
        import hashlib

        sha = hashlib.sha1(b"test content").hexdigest()

        # Should not raise
        downloader._validate_sha(test_file, sha)

    def test_validate_sha_failure(self, downloader: ASEDownloader, tmp_path: Path):
        """Test SHA validation with incorrect hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test content")

        with pytest.raises(ValueError, match="SHA1 mismatch"):
            downloader._validate_sha(test_file, "wrong_hash")

    def test_mesh_dir_creation(
        self,
        tmp_url_dir: Path,
        tmp_output_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test mesh directory is created on initialization."""
        # Remove mesh dir if exists
        mesh_dir = tmp_output_dir / "ase_meshes"
        if mesh_dir.exists():
            import shutil

            shutil.rmtree(mesh_dir)

        config = ASEDownloaderConfig(
            mode="download",
            url_dir=tmp_url_dir,
            output_dir=tmp_output_dir,
        )
        downloader = config.setup_target()

        assert downloader.mesh_dir.exists()
        assert downloader.mesh_dir.is_dir()


class TestASEDownloaderIntegration:
    """Integration tests for downloader."""

    def test_full_config_to_downloader_pipeline(
        self,
        tmp_url_dir: Path,
        tmp_output_dir: Path,
        mock_mesh_urls_json: Path,
        mock_atek_urls_json: Path,
    ):
        """Test complete config → downloader → metadata flow."""
        # Create config
        config = ASEDownloaderConfig(
            mode="download",
            url_dir=tmp_url_dir,
            output_dir=tmp_output_dir,
            metadata_cache_path=tmp_output_dir / "cache.json",
            verbose=False,
        )

        # Create downloader
        downloader = config.setup_target()

        # Verify metadata loaded
        assert len(downloader.metadata.scenes) == 3
        assert len(downloader.metadata.get_scenes_with_meshes()) == 2

        # Verify directories created
        assert downloader.mesh_dir.exists()
        assert config.output_dir.exists()
