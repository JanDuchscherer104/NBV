"""Tests for Streamlit Rerun launch command helpers."""

# ruff: noqa: S101

import socket
from pathlib import Path

import pytest

from aria_nbv.app.rerun_launch import (
    RerunLaunchError,
    RerunLaunchMode,
    build_rerun_offline_spawn_command,
    build_rerun_rollout_command,
    build_rerun_rollout_spawn_command,
    build_rerun_rollout_web_command,
    format_command,
    poll_rerun_launch,
    rerun_web_url,
    resolve_rollout_launch_config,
    start_rerun_launch,
    stop_rerun_launch,
)
from aria_nbv.rerun_inspector._config import RerunOfflineInspectorConfig


def test_rollout_spawn_command_uses_argument_list() -> None:
    command = build_rerun_rollout_spawn_command(
        config_path=Path("cfg.toml"),
        rollout_store=Path("rollouts.zarr"),
        rollout_row_id=42,
    )

    assert command == [
        "nbv-rerun-inspect",
        "--config-path",
        "cfg.toml",
        "--rollout-store",
        "rollouts.zarr",
        "--rollout-row-id",
        "42",
        "--spawn",
    ]


def test_offline_spawn_command_uses_store_override_and_sample_selection() -> None:
    command = build_rerun_offline_spawn_command(
        config_path=Path("cfg.toml"),
        offline_store=Path("vin_offline"),
        split="val",
        index=3,
    )

    assert command == [
        "nbv-rerun-inspect",
        "--config-path",
        "cfg.toml",
        "--offline-store",
        "vin_offline",
        "--split",
        "val",
        "--index",
        "3",
        "--spawn",
    ]


def test_rollout_web_command_saves_and_serves_lan_viewer() -> None:
    command = build_rerun_rollout_web_command(
        config_path=Path("cfg.toml"),
        rollout_store=Path("rollouts.zarr"),
        rollout_row_id=4,
        save_path=Path("row_4.rrd"),
        web_viewer_port=9090,
        ws_server_port=9877,
        lan=True,
    )

    assert command == [
        "nbv-rerun-inspect",
        "--config-path",
        "cfg.toml",
        "--rollout-store",
        "rollouts.zarr",
        "--rollout-row-id",
        "4",
        "--save",
        "row_4.rrd",
        "--serve-web",
        "--web-viewer-port",
        "9090",
        "--ws-server-port",
        "9877",
        "--lan",
    ]


def test_command_format_is_display_only_shell_escaped() -> None:
    assert format_command(["cmd", "path with spaces"]) == "cmd 'path with spaces'"


def test_web_url_includes_recording_proxy_for_new_tab_and_embedding() -> None:
    assert rerun_web_url(web_viewer_port=9090, ws_server_port=9877) == (
        "http://127.0.0.1:9090/?url=rerun%2Bhttp%3A%2F%2Flocalhost%3A9877%2Fproxy"
    )


@pytest.mark.parametrize(
    ("mode", "suffix"),
    [
        (RerunLaunchMode.native_live, ["--spawn"]),
        (RerunLaunchMode.native_view, ["--save", "row.rrd", "--view"]),
        (RerunLaunchMode.save_only, ["--save", "row.rrd"]),
        (
            RerunLaunchMode.serve_web,
            [
                "--save",
                "row.rrd",
                "--serve-web",
                "--web-viewer-port",
                "9090",
                "--ws-server-port",
                "9877",
            ],
        ),
    ],
)
def test_rollout_launch_modes_have_exact_cli_suffixes(mode: RerunLaunchMode, suffix: list[str]) -> None:
    command = build_rerun_rollout_command(
        config_path="cfg.toml",
        rollout_store="rollouts.zarr",
        rollout_row_id=3,
        mode=mode,
        save_path=None if mode is RerunLaunchMode.native_live else "row.rrd",
    )

    assert command == [
        "nbv-rerun-inspect",
        "--config-path",
        "cfg.toml",
        "--rollout-store",
        "rollouts.zarr",
        "--rollout-row-id",
        "3",
        *suffix,
    ]


def test_serve_web_defaults_to_loopback_policy() -> None:
    command = build_rerun_rollout_command(
        config_path="cfg.toml",
        rollout_store="rollouts.zarr",
        rollout_row_id=3,
        mode=RerunLaunchMode.serve_web,
        save_path="row.rrd",
    )

    assert "--lan" not in command


def test_resolved_launch_config_is_deterministic_and_explicit(tmp_path: Path) -> None:
    base_path = tmp_path / "base.toml"
    RerunOfflineInspectorConfig().save_toml(base_path)

    first = resolve_rollout_launch_config(
        base_config_path=base_path,
        artifact_dir=tmp_path / "launches",
        preset="Minimal selected path",
    )
    second = resolve_rollout_launch_config(
        base_config_path=base_path,
        artifact_dir=tmp_path / "launches",
        preset="Minimal selected path",
    )

    assert first.config_path == second.config_path
    assert first.digest == second.digest
    assert first.config_path.read_bytes() == second.config_path.read_bytes()
    assert first.config.rollout_layers.selected_path.included
    assert not first.config.rollout_layers.rollout_candidates.included


class _FakeProcess:
    def __init__(self, *, exit_code: int | None = None) -> None:
        self.pid = 1234
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.exit_code

    def terminate(self) -> None:
        self.terminated = True
        self.exit_code = -15

    def kill(self) -> None:
        self.killed = True
        self.exit_code = -9

    def wait(self, timeout: float | None = None) -> int:
        del timeout
        return int(self.exit_code or 0)


def test_launch_captures_logs_and_reports_running_status(tmp_path: Path) -> None:
    fake = _FakeProcess()

    def factory(command, *, stdout, stderr, start_new_session):
        del command, start_new_session
        stdout.write(b"viewer starting\n")
        stderr.write(b"")
        return fake

    handle = start_rerun_launch(
        ["fake-rerun", "--spawn"],
        artifact_dir=tmp_path,
        config_path=tmp_path / "resolved.toml",
        early_health_seconds=0,
        popen_factory=factory,
    )
    status = poll_rerun_launch(handle)

    assert status.running
    assert status.healthy
    assert status.pid == 1234
    assert "viewer starting" in status.stdout_tail
    assert status.config_path == tmp_path / "resolved.toml"


def test_launch_reports_missing_executable(tmp_path: Path) -> None:
    with pytest.raises(RerunLaunchError, match="not found"):
        start_rerun_launch(
            ["definitely-not-an-aria-nbv-executable"],
            artifact_dir=tmp_path,
            early_health_seconds=0,
        )


def test_launch_rejects_occupied_web_port(tmp_path: Path) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = int(occupied.getsockname()[1])
        with pytest.raises(RerunLaunchError, match="already occupied"):
            start_rerun_launch(
                ["fake", "--web-viewer-port", str(port)],
                artifact_dir=tmp_path,
                early_health_seconds=0,
                popen_factory=lambda *args, **kwargs: _FakeProcess(),
            )


def test_launch_reports_early_exit_with_captured_error(tmp_path: Path) -> None:
    fake = _FakeProcess(exit_code=2)

    def factory(command, *, stdout, stderr, start_new_session):
        del command, stdout, start_new_session
        stderr.write(b"bad config\n")
        return fake

    with pytest.raises(RerunLaunchError, match="bad config"):
        start_rerun_launch(
            ["fake"],
            artifact_dir=tmp_path,
            early_health_seconds=0,
            popen_factory=factory,
        )


def test_save_only_early_success_requires_recording_artifact(tmp_path: Path) -> None:
    rrd_path = tmp_path / "row.rrd"
    rrd_path.write_bytes(b"rrd")
    fake = _FakeProcess(exit_code=0)

    handle = start_rerun_launch(
        ["fake", "--save", str(rrd_path)],
        artifact_dir=tmp_path,
        rrd_path=rrd_path,
        early_health_seconds=0,
        popen_factory=lambda *args, **kwargs: fake,
    )
    status = poll_rerun_launch(handle)

    assert not status.running
    assert status.healthy
    assert status.rrd_exists is True


def test_save_only_success_without_recording_is_not_healthy(tmp_path: Path) -> None:
    fake = _FakeProcess(exit_code=0)

    with pytest.raises(RerunLaunchError, match="recording artifact is missing"):
        start_rerun_launch(
            ["fake", "--save", str(tmp_path / "missing.rrd")],
            artifact_dir=tmp_path,
            rrd_path=tmp_path / "missing.rrd",
            early_health_seconds=0,
            popen_factory=lambda *args, **kwargs: fake,
        )


def test_web_process_exit_is_failure_even_when_recording_exists(tmp_path: Path) -> None:
    rrd_path = tmp_path / "row.rrd"
    rrd_path.write_bytes(b"rrd")
    fake = _FakeProcess(exit_code=0)

    with pytest.raises(RerunLaunchError, match="viewer is no longer available"):
        start_rerun_launch(
            ["fake", "--serve-web"],
            artifact_dir=tmp_path,
            rrd_path=rrd_path,
            url="http://127.0.0.1:9090/",
            early_health_seconds=0,
            popen_factory=lambda *args, **kwargs: fake,
        )


def test_poll_reports_unreachable_web_viewer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProcess()
    handle = start_rerun_launch(
        ["fake"],
        artifact_dir=tmp_path,
        url="http://127.0.0.1:9090/",
        early_health_seconds=0,
        popen_factory=lambda *args, **kwargs: fake,
    )
    monkeypatch.setattr("aria_nbv.app.rerun_launch._url_is_reachable", lambda *args, **kwargs: False)

    status = poll_rerun_launch(handle, verify_url=True)

    assert status.running
    assert not status.healthy
    assert status.url_reachable is False
    assert "unreachable" in status.message


def test_stop_terminates_owned_process(tmp_path: Path) -> None:
    fake = _FakeProcess()
    handle = start_rerun_launch(
        ["fake"],
        artifact_dir=tmp_path,
        early_health_seconds=0,
        popen_factory=lambda *args, **kwargs: fake,
    )

    status = stop_rerun_launch(handle)

    assert fake.terminated
    assert not status.running
