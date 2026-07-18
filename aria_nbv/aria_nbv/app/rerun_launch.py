"""Resolve Rerun launch artifacts, commands, and observable process state.

The Streamlit pages use this module as a presentation-neutral launch boundary:
layer presets become a complete TOML artifact, commands remain argument lists,
and process health is reported through captured logs and optional URL probes.
"""

from __future__ import annotations

import hashlib
import shlex
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from aria_nbv.rerun_inspector._config import RerunOfflineInspectorConfig
from aria_nbv.rerun_inspector._layers import (
    LayerOverride,
    RolloutLayerName,
    RolloutLayerPreset,
    resolve_rollout_layer_config,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence


class RerunLaunchMode(StrEnum):
    """Supported rollout-inspector recording and viewer workflows."""

    native_live = "native_live"
    native_view = "native_view"
    serve_web = "serve_web"
    save_only = "save_only"


class RerunLaunchError(RuntimeError):
    """Report an actionable failure before or immediately after launch."""


@dataclass(frozen=True, slots=True)
class ResolvedRerunLaunchConfig:
    """Resolved launch TOML plus the validated config and content digest."""

    config_path: Path
    """Deterministic hash-named TOML artifact consumed by the CLI."""

    config: RerunOfflineInspectorConfig
    """Validated config whose rollout layer fields are fully expanded."""

    digest: str
    """SHA-256 digest of the rendered TOML content."""


@dataclass(slots=True)
class RerunLaunchProcess:
    """Owned background process and retained launch evidence paths."""

    command: tuple[str, ...]
    """Exact argument vector used to launch the inspector."""

    process: subprocess.Popen[bytes]
    """Owned subprocess handle used for polling, stopping, and restarting."""

    stdout_path: Path
    """Captured standard-output log path."""

    stderr_path: Path
    """Captured standard-error log path."""

    config_path: Path | None = None
    """Resolved per-launch TOML path, when known."""

    rrd_path: Path | None = None
    """Recording artifact path, when the mode saves an ``.rrd``."""

    url: str | None = None
    """Expected web viewer URL for serve-web mode."""

    started_monotonic: float = 0.0
    """Monotonic timestamp captured after successful process creation."""


@dataclass(frozen=True, slots=True)
class RerunLaunchStatus:
    """Current process, artifact, log, and optional viewer reachability state."""

    pid: int
    """Operating-system process identifier."""

    running: bool
    """Whether the child has not exited at the time of polling."""

    exit_code: int | None
    """Child exit status, or ``None`` while running."""

    healthy: bool
    """Whether process state and any requested URL probe succeeded."""

    message: str
    """Concise user-facing health or failure diagnosis."""

    command: tuple[str, ...]
    """Exact launched argument vector."""

    stdout_path: Path
    """Captured standard-output log path."""

    stderr_path: Path
    """Captured standard-error log path."""

    stdout_tail: str
    """Bounded recent standard output for in-app diagnostics."""

    stderr_tail: str
    """Bounded recent standard error for in-app diagnostics."""

    config_path: Path | None
    """Resolved launch TOML path, when provided."""

    rrd_path: Path | None
    """Expected ``.rrd`` artifact path, when provided."""

    rrd_exists: bool | None
    """Whether the expected recording artifact currently exists."""

    url: str | None
    """Expected web viewer URL, when provided."""

    url_reachable: bool | None
    """URL probe result, or ``None`` when no probe was requested."""


def resolve_rollout_launch_config(
    *,
    base_config_path: Path | str,
    artifact_dir: Path | str,
    preset: RolloutLayerPreset | str = RolloutLayerPreset.scientific_context,
    overrides: Mapping[RolloutLayerName | str, LayerOverride] | None = None,
) -> ResolvedRerunLaunchConfig:
    """Persist a deterministic config with an explicit resolved layer policy.

    Args:
        base_config_path: Existing inspector TOML used for non-layer settings.
        artifact_dir: Launch-artifact directory that owns the resolved TOML.
        preset: Named layer-policy starting point.
        overrides: Optional per-layer ``included``/``visible`` overrides.

    Returns:
        Resolved config descriptor. Repeating the same inputs reuses the same
        content-addressed TOML path and bytes.
    """

    cfg = RerunOfflineInspectorConfig.from_toml(Path(base_config_path).expanduser())
    cfg.rollout_layers = resolve_rollout_layer_config(preset, overrides)
    rendered = cfg.to_toml()
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    output_dir = Path(artifact_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / f"rerun_rollout_{digest[:16]}.toml"
    if not config_path.exists() or config_path.read_text(encoding="utf-8") != rendered:
        config_path.write_text(rendered, encoding="utf-8")
    return ResolvedRerunLaunchConfig(config_path=config_path, config=cfg, digest=digest)


def build_rerun_rollout_command(
    *,
    config_path: Path | str,
    rollout_store: Path | str,
    rollout_row_id: int,
    mode: RerunLaunchMode | str,
    save_path: Path | str | None = None,
    web_viewer_port: int = 9090,
    ws_server_port: int = 9877,
    lan: bool = False,
) -> list[str]:
    """Build one exact rollout-inspector command for the selected launch mode."""

    resolved_mode = RerunLaunchMode(mode)
    command = [
        "nbv-rerun-inspect",
        "--config-path",
        str(Path(config_path).expanduser()),
        "--rollout-store",
        str(Path(rollout_store).expanduser()),
        "--rollout-row-id",
        str(int(rollout_row_id)),
    ]
    if resolved_mode is RerunLaunchMode.native_live:
        return [*command, "--spawn"]
    if save_path is None:
        raise ValueError(f"save_path is required for Rerun launch mode {resolved_mode.value!r}.")
    command.extend(("--save", str(Path(save_path).expanduser())))
    if resolved_mode is RerunLaunchMode.native_view:
        command.append("--view")
    elif resolved_mode is RerunLaunchMode.serve_web:
        _validate_port(web_viewer_port, name="web_viewer_port")
        _validate_port(ws_server_port, name="ws_server_port")
        command.extend(
            (
                "--serve-web",
                "--web-viewer-port",
                str(int(web_viewer_port)),
                "--ws-server-port",
                str(int(ws_server_port)),
            )
        )
        if lan:
            command.append("--lan")
    return command


def build_rerun_rollout_spawn_command(
    *,
    config_path: Path | str,
    rollout_store: Path | str,
    rollout_row_id: int,
) -> list[str]:
    """Build the compatibility command for a native live rollout viewer."""

    return build_rerun_rollout_command(
        config_path=config_path,
        rollout_store=rollout_store,
        rollout_row_id=rollout_row_id,
        mode=RerunLaunchMode.native_live,
    )


def build_rerun_rollout_web_command(
    *,
    config_path: Path | str,
    rollout_store: Path | str,
    rollout_row_id: int,
    save_path: Path | str,
    web_viewer_port: int = 9090,
    ws_server_port: int = 9877,
    lan: bool = False,
) -> list[str]:
    """Build the compatibility command for save-then-serve-web mode."""

    return build_rerun_rollout_command(
        config_path=config_path,
        rollout_store=rollout_store,
        rollout_row_id=rollout_row_id,
        mode=RerunLaunchMode.serve_web,
        save_path=save_path,
        web_viewer_port=web_viewer_port,
        ws_server_port=ws_server_port,
        lan=lan,
    )


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


def start_rerun_launch(
    command: Sequence[str],
    *,
    artifact_dir: Path | str,
    config_path: Path | str | None = None,
    rrd_path: Path | str | None = None,
    url: str | None = None,
    early_health_seconds: float = 0.25,
    popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
) -> RerunLaunchProcess:
    """Start a captured background launch and reject immediate failures.

    The executable and explicit web ports are checked before spawning. Standard
    output and error remain available in stable files after the process exits.
    """

    argv = tuple(str(part) for part in command)
    if not argv:
        raise ValueError("Rerun launch command must not be empty.")
    if shutil.which(argv[0]) is None and popen_factory is subprocess.Popen:
        raise RerunLaunchError(f"Rerun inspector executable not found on PATH: {argv[0]!r}.")
    _validate_command_ports_available(argv)
    output_dir = Path(artifact_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()[:16]
    stdout_path = output_dir / f"rerun_launch_{digest}.stdout.log"
    stderr_path = output_dir / f"rerun_launch_{digest}.stderr.log"
    try:
        with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
            process = popen_factory(
                list(argv),
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )
    except FileNotFoundError as exc:
        raise RerunLaunchError(f"Rerun inspector executable not found: {argv[0]!r}.") from exc
    handle = RerunLaunchProcess(
        command=argv,
        process=process,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        config_path=Path(config_path).expanduser() if config_path is not None else None,
        rrd_path=Path(rrd_path).expanduser() if rrd_path is not None else None,
        url=url,
        started_monotonic=time.monotonic(),
    )
    deadline = time.monotonic() + max(float(early_health_seconds), 0.0)
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))
    if process.poll() is not None:
        status = poll_rerun_launch(handle)
        if status.healthy:
            return handle
        detail = status.stderr_tail or status.stdout_tail or status.message
        raise RerunLaunchError(f"Rerun launch exited early with code {status.exit_code}: {detail.strip()}")
    return handle


def poll_rerun_launch(
    handle: RerunLaunchProcess,
    *,
    verify_url: bool = False,
    url_timeout_seconds: float = 0.5,
) -> RerunLaunchStatus:
    """Return current process state, bounded logs, and optional URL health."""

    exit_code = handle.process.poll()
    running = exit_code is None
    rrd_exists = handle.rrd_path.exists() if handle.rrd_path is not None else None
    url_reachable: bool | None = None
    if verify_url and handle.url is not None and running:
        url_reachable = _url_is_reachable(handle.url, timeout_seconds=url_timeout_seconds)
    completed = exit_code == 0 and handle.url is None
    artifact_complete = rrd_exists is not False
    healthy = (running and url_reachable is not False) or (completed and artifact_complete)
    if completed and artifact_complete:
        message = "Rerun launch completed successfully."
    elif completed:
        message = f"Rerun launch completed, but the recording artifact is missing: {handle.rrd_path}."
    elif not running and handle.url is not None:
        message = f"Rerun web-serving process exited with code {exit_code}; the viewer is no longer available."
    elif not running:
        message = f"Rerun process exited with code {exit_code}."
    elif url_reachable is False:
        message = f"Rerun process is running, but the viewer is unreachable at {handle.url}."
    elif url_reachable is True:
        message = f"Rerun viewer is reachable at {handle.url}."
    else:
        message = "Rerun process is running."
    return RerunLaunchStatus(
        pid=int(handle.process.pid),
        running=running,
        exit_code=exit_code,
        healthy=healthy,
        message=message,
        command=handle.command,
        stdout_path=handle.stdout_path,
        stderr_path=handle.stderr_path,
        stdout_tail=_read_log_tail(handle.stdout_path),
        stderr_tail=_read_log_tail(handle.stderr_path),
        config_path=handle.config_path,
        rrd_path=handle.rrd_path,
        rrd_exists=rrd_exists,
        url=handle.url,
        url_reachable=url_reachable,
    )


def stop_rerun_launch(handle: RerunLaunchProcess, *, timeout_seconds: float = 3.0) -> RerunLaunchStatus:
    """Stop the owned launch process, escalating from terminate to kill."""

    if handle.process.poll() is None:
        handle.process.terminate()
        try:
            handle.process.wait(timeout=max(float(timeout_seconds), 0.0))
        except subprocess.TimeoutExpired:
            handle.process.kill()
            handle.process.wait(timeout=max(float(timeout_seconds), 0.0))
    return poll_rerun_launch(handle)


def restart_rerun_launch(
    handle: RerunLaunchProcess,
    *,
    early_health_seconds: float = 0.25,
) -> RerunLaunchProcess:
    """Stop an owned process and relaunch its exact command and evidence paths."""

    stop_rerun_launch(handle)
    return start_rerun_launch(
        handle.command,
        artifact_dir=handle.stdout_path.parent,
        config_path=handle.config_path,
        rrd_path=handle.rrd_path,
        url=handle.url,
        early_health_seconds=early_health_seconds,
    )


def spawn_background_command(command: list[str]) -> subprocess.Popen[bytes]:
    """Spawn a detached compatibility subprocess while capturing no state."""

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


def rerun_web_url(
    *,
    web_viewer_port: int,
    lan: bool = False,
    ws_server_port: int | None = None,
) -> str:
    """Return the expected Rerun web-viewer URL for display.

    When the gRPC/proxy port is known, the URL includes Rerun's ``url`` query
    parameter so a newly opened or embedded viewer connects to the recording
    rather than opening an unconfigured shell.
    """

    host = detect_lan_ip() if lan else "127.0.0.1"
    base = f"http://{host}:{int(web_viewer_port)}/"
    if ws_server_port is None:
        return base
    proxy_host = host if lan else "localhost"
    recording_url = f"rerun+http://{proxy_host}:{int(ws_server_port)}/proxy"
    return f"{base}?{urllib.parse.urlencode({'url': recording_url})}"


def format_command(command: Sequence[str]) -> str:
    """Return a shell-readable command preview for display only."""

    return " ".join(shlex.quote(part) for part in command)


def repo_root() -> Path:
    """Return the ARIA-NBV repository root from the package path."""

    return Path(__file__).resolve().parents[3]


def _validate_port(port: int, *, name: str) -> None:
    if not 0 <= int(port) <= 65535:
        raise ValueError(f"{name} must be in [0, 65535], got {port}.")


def _validate_command_ports_available(command: Sequence[str]) -> None:
    for flag in ("--web-viewer-port", "--ws-server-port"):
        if flag not in command:
            continue
        index = command.index(flag)
        if index + 1 >= len(command):
            raise RerunLaunchError(f"Missing value after {flag}.")
        port = int(command[index + 1])
        if port > 0 and not _port_is_available(port):
            raise RerunLaunchError(f"Cannot launch Rerun: {flag} port {port} is already occupied.")


def _port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", int(port)))
        except OSError:
            return False
    return True


def _url_is_reachable(url: str, *, timeout_seconds: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=max(float(timeout_seconds), 0.01)) as response:  # noqa: S310
            return 200 <= int(response.status) < 500
    except (OSError, urllib.error.URLError, ValueError):
        return False


def _read_log_tail(path: Path, *, max_chars: int = 8_000) -> str:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return content[-max(int(max_chars), 0) :]


__all__ = [
    "ResolvedRerunLaunchConfig",
    "RerunLaunchError",
    "RerunLaunchMode",
    "RerunLaunchProcess",
    "RerunLaunchStatus",
    "build_rerun_offline_spawn_command",
    "build_rerun_rollout_command",
    "build_rerun_rollout_spawn_command",
    "build_rerun_rollout_web_command",
    "detect_lan_ip",
    "format_command",
    "poll_rerun_launch",
    "repo_root",
    "rerun_web_url",
    "resolve_rollout_launch_config",
    "restart_rerun_launch",
    "spawn_background_command",
    "start_rerun_launch",
    "stop_rerun_launch",
]
