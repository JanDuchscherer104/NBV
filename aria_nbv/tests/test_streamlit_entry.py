"""Tests for the Streamlit console-script wrapper."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from aria_nbv.app.app import NbvStreamlitApp
from aria_nbv.app.config import NbvStreamlitAppConfig
from aria_nbv.configs import PathConfig
from aria_nbv.streamlit_app import _build_streamlit_argv, streamlit_entry


def _seed_default_ase_paths(root: Path) -> None:
    shard = root / ".data" / "ase_efm" / "1" / "shards-0000.tar"
    shard.parent.mkdir(parents=True, exist_ok=True)
    shard.write_bytes(b"test")
    taxonomy = root / "external" / "efm3d" / "efm3d" / "config" / "taxonomy" / "atek_to_efm.csv"
    taxonomy.parent.mkdir(parents=True, exist_ok=True)
    taxonomy.write_text("", encoding="utf-8")


def test_streamlit_argv_uses_auto_watcher_by_default(monkeypatch) -> None:
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


def test_streamlit_argv_preserves_file_watcher_cli_override(monkeypatch) -> None:
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


def test_streamlit_argv_preserves_file_watcher_env_override(monkeypatch) -> None:
    monkeypatch.setenv("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "poll")
    monkeypatch.delenv("STREAMLIT_SERVER_RUN_ON_SAVE", raising=False)

    argv = _build_streamlit_argv(Path("/tmp/app.py"), [])

    assert argv == ["streamlit", "run", "--server.runOnSave", "true", "/tmp/app.py"]


def test_streamlit_argv_preserves_run_on_save_cli_and_env_overrides(monkeypatch) -> None:
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


def test_streamlit_entry_rewrites_sys_argv(monkeypatch) -> None:
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
