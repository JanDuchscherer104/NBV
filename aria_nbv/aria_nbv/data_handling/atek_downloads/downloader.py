"""Download orchestration for ASE dataset meshes + ATEK shards."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Literal

import requests
from atek.data_download.atek_data_store_download import download_atek_wds_sequences  # type: ignore[import-untyped]
from pydantic import AliasChoices, Field
from pydantic_settings import (
    CliSettingsSource,
    SettingsConfigDict,
)
from tqdm import tqdm

from ..configs import PathConfig
from ..utils import Console, TargetConfig, Verbosity
from .download_stats import compute_downloaded_atek_stats
from .metadata import ASEMetadata, SceneMetadata


class ASEDownloaderConfig(TargetConfig["ASEDownloader"]):
    """Configuration for ASE downloader with CLI support.

    Supports two CLI modes (explicitly selected via positional `mode`):
        1. Download mode: Download N scenes with meshes + ATEK shards
        2. List mode: List available scenes

    Example (CLI - Download):
        $ python -m aria_nbv.data.downloader download --n_scenes=5 --max_shards=2
        $ python -m aria_nbv.data.downloader download --ns=10 --skip_meshes

    Example (CLI - List):
        $ python -m aria_nbv.data.downloader list --n=10
    """

    @property
    def target_type(self) -> type[ASEDownloader]:
        return ASEDownloader

    # CLI dispatch
    mode: Literal["download", "list"] = Field(default="download", description="Execution mode.", alias="m")

    list_n: int | None = Field(
        default=None,
        alias="n",
        validation_alias=AliasChoices("n", "list-n"),
        description="Number of scenes to show in list mode",
    )

    paths: PathConfig = Field(default_factory=PathConfig)
    output_dir: Path | None = Field(
        default=None, description="Root output dir for downloads. Defaults to `paths.data_root / cfg.mode` "
    )

    # Core configuration
    verbosity: Verbosity = Field(
        default=Verbosity.NORMAL,
        validation_alias=AliasChoices("verbosity", "verbose"),
        description="Verbosity level for logging (0=quiet, 1=normal, 2=verbose).",
    )

    is_debug: bool = Field(default=True)
    """Enable debug logging (forces max verbosity)."""

    prefer_scenes_with_max_shards: bool = True
    """Prefer scenes with maximum shards when limiting number of scenes."""

    # JSON file configuration
    mesh_json_filename: str = Field(default="ase_mesh_download_urls.json")
    """Filename of the mesh download URLs JSON in url_dir. Relative to paths.url_dir."""

    atek_json_filename: str = Field(default="AriaSyntheticEnvironment_ATEK_download_urls.json")
    """Filename of the ATEK download URLs JSON in url_dir. Relative to paths.url_dir."""

    atek_config_name: Literal["efm", "efm_eval", "cubercnn", "cubercnn_eval"] = Field(default="efm_eval", alias="c")
    """ATEK configuration name.

    Notes:
        `efm` and `efm_eval` are shipped as different shard archives (different filenames/SHA
        in the manifest). The snippet payloads are expected to be equivalent, but treat them
        as distinct downloads on disk.
    """

    # Download selection
    n_scenes: int = Field(
        default=100,
        ge=0,
        validation_alias=AliasChoices("n_scenes", "ns"),
    )
    """Number of scenes to download (0 = all available scenes)."""

    max_shards: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("max_shards", "ms"),
    )
    """Maximum shards per scene (None = all shards)."""

    skip_meshes: bool = Field(
        default=False,
        validation_alias=AliasChoices("skip_meshes", "sm"),
    )
    """Skip downloading GT meshes (only download ATEK data)."""

    skip_atek: bool = Field(
        default=False,
        validation_alias=AliasChoices("skip_atek", "sa"),
    )
    """Skip downloading ATEK WDS data (only download meshes)."""

    # ATEK downloader options (from atek_wds_data_downloader.py)
    train_val_split_ratio: float = Field(default=0.9, ge=0.0, le=1.0)
    """Train-validation split ratio for ATEK data."""

    random_seed: int = Field(default=42)
    """Random seed for shuffling ATEK data sequences."""

    download_wds_to_local: bool = Field(default=True)
    """Download WebDataset files to local storage (vs streaming URLs)."""

    overwrite: bool = Field(default=False)
    """Always overwrite existing ATEK files (re-download even if present)."""

    model_config = SettingsConfigDict(
        cli_parse_args=False,  # explicit CLI parsing is triggered via from_cli() to avoid pytest args interference
        cli_exit_on_error=False,
    )

    @classmethod
    def from_cli(cls) -> "ASEDownloaderConfig":
        """Instantiate config using pydantic-settings CLI parser (explicit opt-in)."""

        cli_source = CliSettingsSource(  # type: ignore
            cls,
            cli_parse_args=True,
            cli_ignore_unknown_args=cls.model_config.get("cli_ignore_unknown_args"),
            cli_exit_on_error=cls.model_config.get("cli_exit_on_error"),
            cli_shortcuts=cls.model_config.get("cli_shortcuts"),
        )
        data = cli_source()
        return cls(**data)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
        cli_settings=None,
    ):
        sources = [init_settings]
        if cli_settings is not None:
            sources.append(cli_settings)
        sources.extend([env_settings, dotenv_settings, file_secret_settings])
        return tuple(sources)


class ASEDownloader:
    """Download ASE meshes + ATEK shards."""

    def __init__(self, config: ASEDownloaderConfig):
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__).set_verbosity(config.verbosity).set_debug(config.is_debug)
        )

        # Parse metadata from JSONs
        self.metadata = ASEMetadata(
            url_dir=self.config.paths.url_dir,
            mesh_json_filename=self.config.mesh_json_filename,
            atek_json_filename=self.config.atek_json_filename,
        )
        self.mesh_dir = self.config.paths.ase_meshes

        self.console.log(
            f"Configured paths: mesh_json={self.config.paths.url_dir / self.config.mesh_json_filename}, "
            f"atek_json={self.config.paths.url_dir / self.config.atek_json_filename}, "
            f"mesh_dir={self.mesh_dir}"
        )

    def download_scenes(
        self,
        scenes: list[SceneMetadata] | None = None,
        scene_ids: list[str] | None = None,
        download_meshes: bool = True,
        download_atek: bool = True,
    ) -> None:
        """Download meshes + ATEK data for scenes.

        Args:
            scenes: List of SceneInfo to download
            download_meshes: Download GT meshes
            download_atek: Download ATEK WDS shards
        """
        scenes = scenes or []
        if scene_ids:
            scenes.extend([s for s in self.metadata.get_scenes() if s.scene_id in scene_ids])
        if download_meshes:
            self._download_meshes(scenes)

        if download_atek:
            self._download_atek(scenes)

    # convenience wrappers for CLI
    def download_meshes(self, scene_ids: list[str] | None = None, overwrite: bool = False) -> None:
        scenes = [s for s in self.metadata.get_scenes() if not scene_ids or s.scene_id in scene_ids]
        self.config.overwrite = overwrite
        self._download_meshes(scenes)

    def download_atek(self, scene_ids: list[str] | None = None) -> None:
        scenes = [s for s in self.metadata.get_scenes() if not scene_ids or s.scene_id in scene_ids]
        self._download_atek(scenes)

    def _download_meshes(self, scenes: list[SceneMetadata]) -> None:
        """Download GT meshes from CDN.

        Adapted from ATEK's ase_mesh_downloader.py to align with our design patterns.
        Downloads, verifies SHA, extracts, and moves mesh files to output directory.
        """
        mesh_dir = self.config.paths.ase_meshes
        mesh_dir.mkdir(parents=True, exist_ok=True)

        self.console.log(f"Mesh download destination: {mesh_dir}")

        # Check which meshes already exist
        scenes_to_download = []
        for scene in scenes:
            mesh_path = mesh_dir / f"scene_ply_{scene.scene_id}.ply"
            if mesh_path.exists():
                self.console.log(f"Scene {scene.scene_id}: mesh already exists at {mesh_path}, skipping")
            else:
                scenes_to_download.append(scene)

        if not scenes_to_download:
            self.console.log("All meshes already downloaded ✓")
            return

        self.console.log(
            f"Downloading {len(scenes_to_download)} GT meshes (skipping {len(scenes) - len(scenes_to_download)} existing)..."
        )

        # Download each mesh
        for scene in tqdm(
            scenes_to_download,
            desc="Downloading meshes",
            disable=self.config.verbosity <= Verbosity.QUIET,
        ):
            zip_filename = f"scene_ply_{scene.scene_id}.zip"
            ply_filename = f"scene_ply_{scene.scene_id}.ply"

            assert isinstance(scene, SceneMetadata)
            try:
                zip_path = self._download_file(scene.mesh_url, dest_path=Path(zip_filename))  # type: ignore[arg-type]
                self.console.dbg(f"Downloaded zip to {zip_path}")

                # Verify SHA1 checksum
                self._validate_sha(zip_path, scene.mesh_sha)

                # Extract PLY from ZIP
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(mesh_dir)

                # Move to output directory
                ply_path = mesh_dir / ply_filename
                if ply_path.exists():
                    self.console.log(f"Scene {scene.scene_id}: mesh downloaded ✓ -> {ply_path}")
                else:
                    self.console.warn(f"Scene {scene.scene_id}: PLY not found in ZIP")

            except Exception as e:
                self.console.error(f"Scene {scene.scene_id}: download failed - {e}")

            finally:
                Path(zip_filename).unlink(missing_ok=True)

        self.console.log("✓ Mesh downloads complete")

    def _download_atek(self, scenes: list[SceneMetadata]) -> None:
        """Download ATEK WDS shards using ATEK's download_atek_wds_sequences."""
        self.console.log(f"Downloading ATEK data for {len(scenes)} scenes...")

        # Load ATEK JSON and filter to selected scenes
        atek_json = self.config.paths.url_dir / self.config.atek_json_filename
        if not atek_json.exists():
            raise FileNotFoundError(f"ATEK JSON not found: {atek_json}")

        self.console.log(f"Using ATEK URL json: {atek_json}")

        with atek_json.open() as f:
            atek_data = json.load(f)

        # Filter wds_file_urls to only include our scenes AND shards
        config_data = atek_data["atek_data_for_all_configs"][self.config.atek_config_name]
        all_urls = config_data["wds_file_urls"]

        filtered_urls = {}
        for scene in scenes:
            if scene.scene_id not in all_urls:
                continue

            # Only include shards that are in scene.shard_ids
            scene_shards = all_urls[scene.scene_id]
            filtered_shards = {
                shard_key: shard_info
                for shard_key, shard_info in scene_shards.items()
                if shard_key.replace("_tar", "") in scene.shard_ids
            }

            if filtered_shards:
                filtered_urls[scene.scene_id] = filtered_shards

        if not filtered_urls:
            self.console.warn("No ATEK data found for selected scenes")
            return

        # Create filtered JSON for ATEK downloader
        filtered_data = {
            "raw_dataset_name": atek_data["raw_dataset_name"],
            "raw_dataset_release_version": atek_data["raw_dataset_release_version"],
            "atek_data_for_all_configs": {
                self.config.atek_config_name: {
                    **config_data,
                    "wds_file_urls": filtered_urls,
                }
            },
        }

        # Write temporary JSON
        tmp_json = self.config.paths.url_dir / f"_temp_atek_{self.config.atek_config_name}.json"
        with tmp_json.open("w") as f:
            json.dump(filtered_data, f)

        self.console.dbg(f"Temp filtered ATEK json written to {tmp_json}")

        try:
            output_dir = self.config.paths.resolve_atek_data_dir(self.config.atek_config_name)
            self.console.log(f"ATEK output dir: {output_dir}")

            # Call ATEK downloader directly (no subprocess)
            download_atek_wds_sequences(
                config_name=self.config.atek_config_name,
                input_json_path=str(tmp_json),
                train_val_split_ratio=self.config.train_val_split_ratio,
                random_seed=self.config.random_seed,
                output_folder_path=str(output_dir),
                max_num_sequences=len(filtered_urls) if filtered_urls else None,
                download_wds_to_local=self.config.download_wds_to_local,
                overwrite=self.config.overwrite,
            )

            self.console.log("✓ ATEK data downloaded")

        finally:
            tmp_json.unlink(missing_ok=True)

    def _validate_sha(self, path: Path, expected_sha: str | None) -> None:
        if not expected_sha:
            return
        computed = hashlib.sha1(path.read_bytes()).hexdigest()
        if computed != expected_sha:
            raise ValueError(f"SHA1 mismatch for {path}: {computed} != {expected_sha}")

    def download_scenes_with_meshes(self, min_shards: int, config: str, overwrite: bool) -> None:
        """Download scenes that have meshes and at least `min_shards` shards for a given config."""
        scenes = self.metadata.filter_scenes(min_shards=min_shards, require_mesh=True, config=config)
        self.config.overwrite = overwrite
        scene_ids = [s.scene_id for s in scenes]
        self.download_scenes(
            scenes=scenes,
            scene_ids=scene_ids,
            download_meshes=not self.config.skip_meshes,
            download_atek=not self.config.skip_atek,
        )

    def _download_file(self, url: str, dest_path: Path) -> Path:
        """Download URL to destination path (separate for patching in tests)."""

        resp = requests.get(url)
        resp.raise_for_status()
        dest_path.write_bytes(resp.content)
        return dest_path


# ============================================================================
# CLI Entry Points
# ============================================================================


def cli_download(config: ASEDownloaderConfig | None = None) -> None:
    """CLI entry point for downloading scenes.

    Usage:
        python -m aria_nbv.data.downloader download --n_scenes=5 --max_shards=2
        python -m aria_nbv.data.downloader download --ns=10 --skip_meshes
    """
    config = config or ASEDownloaderConfig()
    console = Console.with_prefix("DownloaderCLI").set_verbosity(config.verbosity).set_debug(config.is_debug)
    downloader = config.setup_target()

    # Get scenes
    n = None if config.n_scenes == 0 else config.n_scenes
    if config.skip_meshes:
        scenes = downloader.metadata.get_scenes()
    else:
        scenes = downloader.metadata.filter_scenes(
            min_shards=0,
            require_mesh=True,
            config=config.atek_config_name,
        )
    # apply shard cap
    if config.max_shards:
        scenes = [
            SceneMetadata(
                scene_id=s.scene_id,
                has_gt_mesh=s.has_gt_mesh,
                mesh_url=s.mesh_url,
                mesh_sha=s.mesh_sha,
                shard_count=min(s.shard_count, config.max_shards),
                shard_ids=s.shard_ids[: config.max_shards],
                atek_config=s.atek_config,
                total_frames=s.total_frames,
            )
            for s in scenes
        ]
    # prefer richest scenes first
    if config.prefer_scenes_with_max_shards:
        scenes = sorted(scenes, key=lambda s: (-s.shard_count, s.scene_id))
    # limit number of scenes
    if n:
        scenes = scenes[:n]

    console.log("=" * 60)
    console.log("ASE Dataset Downloader")
    console.log("=" * 60)
    console.log(f"Downloading {len(scenes)} scenes:")
    for scene in scenes[:10]:  # Show first 10
        console.log(f"  - Scene {scene.scene_id}: {len(scene.shard_ids)} shards")
    if len(scenes) > 10:
        console.log(f"  ... and {len(scenes) - 10} more")

    total_shards = sum(len(s.shard_ids) for s in scenes)
    mesh_note = " (mesh-required)" if not config.skip_meshes else ""
    console.log(f"\nTotal: {len(scenes)} scenes{mesh_note}, {total_shards} shards")

    # Download
    downloader.download_scenes(
        scenes=scenes,
        download_meshes=not config.skip_meshes,
        download_atek=not config.skip_atek,
    )

    console.log("=" * 60)
    console.log("✓ Download complete!")
    console.log("=" * 60)


def cli_list(config: ASEDownloaderConfig, n: int | None = None) -> None:
    """CLI entry point for listing scenes.

    Args:
        n: Number of scenes to list (None = all)

    Usage:
        python -m aria_nbv.data.downloader list
        python -m aria_nbv.data.downloader list --n=10
    """
    console = Console.with_prefix("DownloaderCLI").set_verbosity(config.verbosity).set_debug(config.is_debug)
    downloader = config.setup_target()

    console.log(f"ATEK config: {config.atek_config_name}")

    all_scenes = downloader.metadata.get_scenes_with_meshes(config=config.atek_config_name)
    total_shards = sum(scene.shard_count for scene in all_scenes)
    scenes = all_scenes
    if config.prefer_scenes_with_max_shards:
        scenes = sorted(scenes, key=lambda s: (-s.shard_count, s.scene_id))
    if n:
        scenes = scenes[:n]
    shown_shards = sum(scene.shard_count for scene in scenes)

    console.log("=" * 60)
    console.log("ASE Dataset - Available Scenes")
    console.log("=" * 60)
    console.log(f"Total scenes with GT meshes: {len(all_scenes)}")
    console.log(f"\nShowing {len(scenes)} scenes:")
    for scene in scenes:
        console.log(f"  Scene {scene.scene_id}: {len(scene.shard_ids)} shards")
    console.log(f"\nTotal shards (all GT-mesh scenes): {total_shards}")
    if n is not None and len(scenes) != len(all_scenes):
        console.log(f"Total shards (shown scenes): {shown_shards}")

    console.log("\nDownloaded overview (GT-mesh scenes):")
    for cfg_name in ("efm", "efm_eval"):
        stats = compute_downloaded_atek_stats(
            metadata=downloader.metadata,
            data_root=config.paths.data_root,
            config_name=cfg_name,
        )
        pct = 0.0 if stats.expected_shards == 0 else (100.0 * stats.downloaded_shards / stats.expected_shards)
        snippet_note = ""
        if stats.snippets_per_shard is not None:
            suffix = " (estimated)" if stats.snippet_count_is_estimate else ""
            snippet_note = f", {stats.downloaded_snippets} snippets ({stats.snippets_per_shard}/shard{suffix})"
        else:
            snippet_note = f", {stats.downloaded_snippets} snippets"
        console.log(
            f"  - {cfg_name}: {stats.downloaded_shards}/{stats.expected_shards} shards "
            f"({pct:.1f}%), {stats.downloaded_scenes}/{stats.expected_scenes} scenes{snippet_note}"
        )
    console.log("=" * 60)


def main() -> None:
    """Main CLI entry point with mode-based dispatching."""

    config = ASEDownloaderConfig.from_cli()
    console = Console.with_prefix("DownloaderCLI").set_verbosity(config.verbosity)

    match config.mode:
        case "list":
            cli_list(config=config, n=config.list_n)
        case "download":
            cli_download(config=config)
        case _:
            console.error(f"Unsupported mode: {config.mode}")


if __name__ == "__main__":
    main()
