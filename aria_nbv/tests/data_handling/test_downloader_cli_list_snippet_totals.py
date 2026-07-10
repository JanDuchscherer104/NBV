"""Tests for the downloader CLI list output."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.atek_downloads.downloader import ASEDownloaderConfig, cli_list
from aria_nbv.utils import Verbosity

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


@pytest.fixture(autouse=True)
def _restore_path_config() -> Iterator[None]:
    snapshot = PathConfig().model_dump()
    yield
    PathConfig(**snapshot)


def test_cli_list_prints_total_snippets(
    tmp_path: Path,
    tmp_url_dir: Path,
    mock_mesh_urls_json: Path,
    mock_atek_urls_json: Path,
    capsys,
) -> None:
    paths = PathConfig(
        root=tmp_path,
        data_root=tmp_path / "data",
        checkpoints=tmp_path / "checkpoints",
        wandb=tmp_path / "wandb",
        configs_dir=tmp_path / "configs",
        url_dir=tmp_url_dir,
        metadata_cache=tmp_path / "metadata_cache.json",
        ase_meshes=tmp_path / "ase_meshes",
        processed_meshes=tmp_path / "ase_meshes_processed",
        external_dir=tmp_path / "external",
    )
    config = ASEDownloaderConfig(
        m="list",
        paths=paths,
        c="efm",
        verbosity=Verbosity.NORMAL,
        is_debug=False,
    )

    cli_list(config=config)

    captured = capsys.readouterr()
    text = _strip_ansi(captured.out + captured.err)

    assert "Total shards (all GT-mesh scenes): 5" in text


def test_cli_list_prints_total_snippets_for_shown_scenes(
    tmp_path: Path,
    tmp_url_dir: Path,
    mock_mesh_urls_json: Path,
    mock_atek_urls_json: Path,
    capsys,
) -> None:
    paths = PathConfig(
        root=tmp_path,
        data_root=tmp_path / "data",
        checkpoints=tmp_path / "checkpoints",
        wandb=tmp_path / "wandb",
        configs_dir=tmp_path / "configs",
        url_dir=tmp_url_dir,
        metadata_cache=tmp_path / "metadata_cache.json",
        ase_meshes=tmp_path / "ase_meshes",
        processed_meshes=tmp_path / "ase_meshes_processed",
        external_dir=tmp_path / "external",
    )
    config = ASEDownloaderConfig(
        m="list",
        paths=paths,
        c="efm",
        verbosity=Verbosity.NORMAL,
        is_debug=False,
    )

    cli_list(config=config, n=1)

    captured = capsys.readouterr()
    text = _strip_ansi(captured.out + captured.err)

    assert "Total shards (all GT-mesh scenes): 5" in text
    assert "Total shards (shown scenes): 3" in text
