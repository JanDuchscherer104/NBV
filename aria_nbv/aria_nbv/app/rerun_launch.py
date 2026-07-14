"""Command builders and process helpers for launching Rerun inspectors.

The module provides argument-safe native and web commands, detached spawning,
display-only shell formatting, LAN URL hints, and repository-root discovery.
"""

from __future__ import annotations

import shlex
import socket
import subprocess
from pathlib import Path


def build_rerun_rollout_spawn_command(
    *,
    config_path: Path | str,
    rollout_store: Path | str,
    rollout_row_id: int,
) -> list[str]:
    """Build the inspector command for a single rollout-store row."""

    return [
        "nbv-rerun-inspect",
        "--config-path",
        str(Path(config_path).expanduser()),
        "--rollout-store",
        str(Path(rollout_store).expanduser()),
        "--rollout-row-id",
        str(int(rollout_row_id)),
        "--spawn",
    ]


def build_rerun_rollout_web_command(
    *,
    config_path: Path | str,
    rollout_store: Path | str,
    rollout_row_id: int,
    save_path: Path | str,
    web_viewer_port: int = 9090,
    ws_server_port: int = 9877,
    lan: bool = True,
) -> list[str]:
    """Build an inspector command that saves and serves one rollout row on the web."""

    command = [
        "nbv-rerun-inspect",
        "--config-path",
        str(Path(config_path).expanduser()),
        "--rollout-store",
        str(Path(rollout_store).expanduser()),
        "--rollout-row-id",
        str(int(rollout_row_id)),
        "--save",
        str(Path(save_path).expanduser()),
        "--serve-web",
        "--web-viewer-port",
        str(int(web_viewer_port)),
        "--ws-server-port",
        str(int(ws_server_port)),
    ]
    if lan:
        command.append("--lan")
    return command


def build_rerun_offline_spawn_command(
    *,
    config_path: Path | str,
    offline_store: Path | str,
    split: str,
    index: int,
) -> list[str]:
    """Build the inspector command for a VIN offline sample."""

    return [
        "nbv-rerun-inspect",
        "--config-path",
        str(Path(config_path).expanduser()),
        "--offline-store",
        str(Path(offline_store).expanduser()),
        "--split",
        str(split),
        "--index",
        str(int(index)),
        "--spawn",
    ]


def spawn_background_command(command: list[str]) -> subprocess.Popen[bytes]:
    """Spawn a detached subprocess from an argument list."""

    return subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def detect_lan_ip() -> str:
    """Return the likely LAN-facing IPv4 address for browser URL hints."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def rerun_web_url(*, web_viewer_port: int, lan: bool = True) -> str:
    """Return the expected Rerun web-viewer URL for display."""

    host = detect_lan_ip() if lan else "127.0.0.1"
    return f"http://{host}:{int(web_viewer_port)}/"


def format_command(command: list[str]) -> str:
    """Return a shell-readable command preview for display only."""

    return " ".join(shlex.quote(part) for part in command)


def repo_root() -> Path:
    """Return the ARIA-NBV repository root from the package path."""

    return Path(__file__).resolve().parents[3]


__all__ = [
    "build_rerun_offline_spawn_command",
    "build_rerun_rollout_spawn_command",
    "build_rerun_rollout_web_command",
    "detect_lan_ip",
    "format_command",
    "rerun_web_url",
    "repo_root",
    "spawn_background_command",
]
