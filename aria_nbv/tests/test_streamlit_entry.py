"""Tests for the Streamlit console-script wrapper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from aria_nbv.app.app import NbvStreamlitApp
from aria_nbv.app.config import NbvStreamlitAppConfig
from aria_nbv.configs import PathConfig
from aria_nbv.streamlit_app import _build_streamlit_argv, _extract_config_path, _load_app_config, streamlit_entry
from aria_nbv.utils import BaseConfig


def _seed_default_ase_paths(root: Path) -> None:
    shard = root / ".data" / "ase_efm" / "1" / "shards-0000.tar"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"test")
    taxonomy = root / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "atek_to_efm.csv"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("", encoding="utf-8")


def test_streamlit_argv_uses_auto_watcher_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)

    argv = _build_streamlit_argv(Path("/tmp/app.py"), [])

    assert argv == [
        "streamlit",
        "run",
        "--server.runOnSave",
        "true",
        "--server.fileWatcherType",
        "auto",
        "/tmp/app.py",
    ]


def test_streamlit_argv_preserves_file_watcher_cli_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)

    argv = _build_streamlit_argv(
        Path("/tmp/app.py"),
        ["--server.fileWatcherType=poll", "--server.port", "8502", "--", "--debug"],
    )

    assert argv == [
        "streamlit",
        "run",
        "--server.runOnSave",
        "true",
        "--server.fileWatcherType=poll",
        "--server.port",
        "8502",
        "/tmp/app.py",
        "--",
        "--debug",
    ]


def test_streamlit_argv_preserves_file_watcher_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "poll")
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)

    argv = _build_streamlit_argv(Path("/tmp/app.py"), [])

    assert argv == ["streamlit", "run", "--server.runOnSave", "true", "/tmp/app.py"]


def test_streamlit_argv_preserves_run_on_save_cli_and_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)

    argv = _build_streamlit_argv(Path("/tmp/app.py"), ["--server.runOnSave=false"])

    assert argv == [
        "streamlit",
        "run",
        "--server.fileWatcherType",
        "auto",
        "--server.runOnSave=false",
        "/tmp/app.py",
    ]

    monkeypatch.setenv("STREAMLIT_SERVER_RUN_ON_SAVE", "false")
    argv = _build_streamlit_argv(Path("/tmp/app.py"), [])

    assert argv == ["streamlit", "run", "--server.fileWatcherType", "auto", "/tmp/app.py"]


def test_streamlit_entry_rewrites_sys_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_argv: list[str] = []

    def fake_streamlit_main() -> None:
        captured_argv[:] = sys.argv

    monkeypatch.delenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", raising=False)
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)
    monkeypatch.setattr("streamlit.web.cli.main", fake_streamlit_main)
    monkeypatch.setattr(sys, "argv", ["nbv-st"])

    streamlit_entry()

    assert captured_argv[:6] == [
        "streamlit",
        "run",
        "--server.runOnSave",
        "true",
        "--server.fileWatcherType",
        "auto",
    ]
    assert captured_argv[6].endswith("streamlit_app.py")


def test_streamlit_app_config_targets_streamlit_app(tmp_path: Path) -> None:
    original_paths = PathConfig().model_dump()
    _seed_default_ase_paths(tmp_path)
    try:
        PathConfig(data_root=tmp_path / ".data", external_dir=tmp_path / "external")
        target_type = NbvStreamlitAppConfig().target_type
    finally:
        PathConfig(**original_paths)

    assert target_type is NbvStreamlitApp


def test_streamlit_app_config_loads_and_validates_shared_s2_recipe(tmp_path: Path) -> None:
    original_paths = PathConfig().model_dump()
    _seed_default_ase_paths(tmp_path)
    recipe_path = tmp_path / ".configs" / "reports" / "s2.toml"
    recipe_path.parent.mkdir(parents=True)
    recipe_path.write_text(
        """schema_version = "aria-nbv-report-config-v1"
evidence_status = "pilot"

[sources.rollout]
store_paths = ["store.zarr"]

[[sections]]
kind = "rollout_s2"
id = "s2"
channels = ["movement"]

[sections.analysis]
azimuth_bins = 12
elevation_bins = 6
projection_limit = 32
""",
        encoding="utf-8",
    )
    try:
        PathConfig(data_root=tmp_path / ".data", external_dir=tmp_path / "external")
        config = NbvStreamlitAppConfig(s2_report_recipe_path=Path(".configs/reports/s2.toml"))
        recipe, resolved = config.load_s2_report_recipe(root=tmp_path)
    finally:
        PathConfig(**original_paths)

    assert resolved == recipe_path
    assert recipe.rollout_s2_section("s2").analysis.model_dump() == {
        "azimuth_bins": 12,
        "elevation_bins": 6,
        "projection_limit": 32,
    }


def test_streamlit_entry_loads_canonical_or_explicit_app_config(tmp_path: Path) -> None:
    class AppConfigProbe(BaseConfig):
        s2_report_section_id: str = "default"

    canonical = tmp_path / ".configs" / "streamlit_app.toml"
    explicit = tmp_path / "custom.toml"
    canonical.parent.mkdir(parents=True)
    canonical.write_text('s2_report_section_id = "canonical"\n', encoding="utf-8")
    explicit.write_text('s2_report_section_id = "explicit"\n', encoding="utf-8")

    assert _load_app_config([], config_type=AppConfigProbe, root=tmp_path).s2_report_section_id == "canonical"
    assert (
        _load_app_config(
            ["--config-path", explicit.as_posix()],
            config_type=AppConfigProbe,
            root=tmp_path,
        ).s2_report_section_id
        == "explicit"
    )
    assert _extract_config_path(["--config-path=custom.toml"]) == Path("custom.toml")
    with pytest.raises(ValueError, match="only once"):
        _extract_config_path(["--config-path", "one.toml", "--config-path=two.toml"])


def test_streamlit_entry_module_is_import_light() -> None:
    """Importing the console entrypoint must not initialize Streamlit panels."""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import aria_nbv.streamlit_app; "
                "print('aria_nbv.app.app' in sys.modules); "
                "print(any(name.startswith('aria_nbv.app.panels') for name in sys.modules))"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["False", "False"]
    assert "No runtime found" not in result.stderr
