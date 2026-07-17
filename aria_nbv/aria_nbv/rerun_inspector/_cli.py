"""Select immutable VIN or rollout rows and orchestrate Rerun inspection.

This module owns CLI override precedence, output-mode validation, optional
native/web viewer launch, and the top-level offline-inspector runtime. Geometry
and labels are read from existing stores; the CLI writes only the configured
Rerun recording or connects to the requested viewer sink.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import click
import typer

from aria_nbv.data_handling.identifiers import compact_ase_atek_sample_id
from aria_nbv.utils import Console
from aria_nbv.utils.config_paths import resolve_config_toml_path
from aria_nbv.utils.typer_cli import run_typer_app

from ._config import RerunOfflineInspectorConfig
from ._loggers import RerunOfflineLogger
from ._metadata import collect_visual_inventory, validate_required_inventory
from ._sample import select_rerun_sample
from ._session import RerunModule


class Split(StrEnum):
    """VIN offline store splits accepted by the Rerun CLI."""

    all = "all"
    train = "train"
    val = "val"


class RolloutContextMode(StrEnum):
    """VIN context policies for rollout-store inspection."""

    auto = "auto"
    required = "required"
    off = "off"


@dataclass(frozen=True)
class RerunCliOptions:
    """Typed, side-effect-free CLI overrides applied to a loaded TOML config.

    Selection fields identify immutable VIN or rollout source rows. Output
    fields choose one recording sink or a post-save viewer process; resolving
    these values does not itself initialize Rerun or read store payload arrays.
    """

    config_path: Path
    """TOML source path whose resolved values provide non-overridden defaults."""

    split: Split | None
    """Optional VIN split override for index-based sample selection."""

    index: int | None
    """Optional zero-based index within ``split``."""

    sample_id: str | None
    """Optional stable VIN sample key, taking precedence over other selectors."""

    scene_id: str | None
    """Optional ASE scene identity paired with ``snippet_id``."""

    snippet_id: str | None
    """Optional ASE/ATEK snippet identity paired with ``scene_id``."""

    candidate_index: int | None
    """Optional stored VIN candidate-prefix row selected for detail layers."""

    offline_store: Path | None
    """Optional immutable VIN offline-store path override."""

    rollout_store: Path | None
    """Optional standalone rollout Zarr store opened read-only for inspection."""

    rollout_index: int
    """Zero-based rollout-table position used unless a row id is supplied."""

    rollout_row_id: int | None
    """Optional stable ``rollouts/rollout_row_id`` taking index precedence."""

    rollout_context: RolloutContextMode | None
    """Optional policy for joining rollout facts back to immutable VIN context."""

    save_path: Path | None
    """Optional owned ``.rrd`` destination for save output."""

    save_requested: bool
    """Whether CLI flags explicitly select save mode."""

    spawn: bool
    """Whether CLI flags explicitly select a spawned local viewer sink."""

    connect_addr: str | None
    """Optional existing Rerun gRPC endpoint."""

    connect_requested: bool
    """Whether CLI flags explicitly select gRPC connect mode."""

    view: bool
    """Whether to save then open the recording in the native viewer."""

    serve_web: bool
    """Whether to save then serve the recording with Rerun's web viewer."""

    web_viewer_port: int
    """Requested HTTP port for the web viewer; zero delegates allocation."""

    ws_server_port: int
    """Requested websocket port for the web viewer; zero delegates allocation."""

    lan: bool
    """Whether web serving binds beyond loopback and prints a LAN URL hint."""


_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}
app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Inspect one immutable VIN offline sample or rollout Zarr row in Rerun.",
    pretty_exceptions_show_locals=False,
)


def main(argv: list[str] | None = None) -> None:
    """Run ``nbv-rerun-inspect`` from a TOML config and CLI overrides."""

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(app, _normalize_optional_value_flags(raw_argv), prog_name="nbv-rerun-inspect")


@app.command()
def rerun_inspect_command(
    config_path: Annotated[
        Path,
        typer.Option("--config-path", help="Path to a RerunOfflineInspectorConfig TOML file."),
    ],
    split: Annotated[Split | None, typer.Option("--split", help="Override selection.split.")] = None,
    index: Annotated[int | None, typer.Option("--index", min=0, help="Override selection.index.")] = None,
    sample_id: Annotated[str | None, typer.Option("--sample-id", help="Override selection.sample_key.")] = None,
    scene_id: Annotated[str | None, typer.Option("--scene-id", help="Override selection.scene_id.")] = None,
    snippet_id: Annotated[str | None, typer.Option("--snippet-id", help="Override selection.snippet_id.")] = None,
    candidate_index: Annotated[
        int | None,
        typer.Option("--candidate-index", min=0, help="Override candidate.selected_index for detail layers."),
    ] = None,
    offline_store: Annotated[
        Path | None,
        typer.Option("--offline-store", help="Override dataset.offline.store.store_dir."),
    ] = None,
    rollout_store: Annotated[
        Path | None,
        typer.Option("--rollout-store", help="Inspect a standalone rollouts.zarr replay store."),
    ] = None,
    rollout_index: Annotated[
        int,
        typer.Option("--rollout-index", min=0, help="Zero-based rollout row position for --rollout-store."),
    ] = 0,
    rollout_row_id: Annotated[
        int | None,
        typer.Option("--rollout-row-id", min=0, help="Explicit rollouts/rollout_row_id for --rollout-store."),
    ] = None,
    rollout_context: Annotated[
        RolloutContextMode | None,
        typer.Option("--rollout-context", help="VIN context policy for --rollout-store."),
    ] = None,
    save_path: Annotated[
        Path | None,
        typer.Option("--save", help="Override output mode to save and optionally set an .rrd path."),
    ] = None,
    save_mode: Annotated[
        bool,
        typer.Option("--save-mode", hidden=True),
    ] = False,
    spawn: Annotated[bool, typer.Option("--spawn", help="Override output mode to spawn a local viewer.")] = False,
    connect_addr: Annotated[
        str | None,
        typer.Option("--connect", help="Override output mode to connect over Rerun gRPC."),
    ] = None,
    connect_mode: Annotated[
        bool,
        typer.Option("--connect-mode", hidden=True),
    ] = False,
    view: Annotated[
        bool,
        typer.Option("--view", help="Save the .rrd and open it in the native Rerun viewer in the foreground."),
    ] = False,
    serve_web: Annotated[
        bool,
        typer.Option("--serve-web", help="Save the .rrd and serve it with Rerun's web viewer in the foreground."),
    ] = False,
    web_viewer_port: Annotated[
        int,
        typer.Option("--web-viewer-port", min=0, max=65535, help="Rerun web viewer HTTP port for --serve-web."),
    ] = 0,
    ws_server_port: Annotated[
        int,
        typer.Option("--ws-server-port", min=0, max=65535, help="Rerun websocket port for --serve-web."),
    ] = 0,
    lan: Annotated[
        bool,
        typer.Option("--lan", help="With --serve-web, bind to 0.0.0.0 and print a LAN URL hint."),
    ] = False,
) -> None:
    """Inspect one configured VIN sample or rollout chain in a Rerun session.

    CLI overrides are validated before loading heavy arrays or initializing a
    recording. Exactly one save, spawn, or connect sink is selected; optional
    native/web viewing occurs only after an ``.rrd`` recording is written.
    """

    options = RerunCliOptions(
        config_path=config_path,
        split=split,
        index=index,
        sample_id=sample_id,
        scene_id=scene_id,
        snippet_id=snippet_id,
        candidate_index=candidate_index,
        offline_store=offline_store,
        rollout_store=rollout_store,
        rollout_index=rollout_index,
        rollout_row_id=rollout_row_id,
        rollout_context=rollout_context,
        save_path=save_path,
        save_requested=save_mode or save_path is not None,
        spawn=spawn,
        connect_addr=connect_addr,
        connect_requested=connect_mode or connect_addr is not None,
        view=view,
        serve_web=serve_web,
        web_viewer_port=web_viewer_port,
        ws_server_port=ws_server_port,
        lan=lan,
    )
    _validate_viewer_args(options)
    config_path = resolve_config_toml_path(options.config_path)
    cfg = RerunOfflineInspectorConfig.from_toml(config_path)
    cfg = _apply_overrides(cfg, options)
    if options.rollout_store is not None:
        from ._rollout_zarr import run_rollout_zarr_inspector

        run_rollout_zarr_inspector(
            cfg,
            store_dir=options.rollout_store,
            rollout_index=options.rollout_index,
            rollout_row_id=options.rollout_row_id,
        )
    else:
        run_inspector(cfg)
    if options.view or options.serve_web:
        _run_viewer_command(
            _viewer_command(
                save_path=cfg.output.save_path,
                serve_web=options.serve_web,
                lan=options.lan,
                web_viewer_port=options.web_viewer_port,
                ws_server_port=options.ws_server_port,
            ),
            lan=options.lan,
            web_viewer_port=options.web_viewer_port,
        )


def _normalize_optional_value_flags(argv: list[str]) -> list[str]:
    """Map optional-value flags to hidden boolean flags when no value is supplied."""

    replacements = {"--save": "--save-mode", "--connect": "--connect-mode"}
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in replacements and (index + 1 >= len(argv) or argv[index + 1].startswith("-")):
            normalized.append(replacements[token])
            index += 1
            continue
        normalized.append(token)
        index += 1
    return normalized


def _validate_viewer_args(options: RerunCliOptions) -> None:
    """Reject incompatible CLI viewer and SDK-sink combinations."""

    if options.view and options.serve_web:
        raise click.UsageError("--view and --serve-web are mutually exclusive.")
    if (options.view or options.serve_web) and (options.spawn or options.connect_requested):
        raise click.UsageError(
            "--view/--serve-web are post-save viewer modes and cannot be combined with --spawn/--connect."
        )
    if options.lan and not options.serve_web:
        raise click.UsageError("--lan requires --serve-web.")


def _apply_overrides(config: RerunOfflineInspectorConfig, options: RerunCliOptions) -> RerunOfflineInspectorConfig:
    """Apply CLI overrides while preserving TOML defaults."""

    cfg = config.model_copy(deep=True)
    selection_updates: dict[str, object] = {}
    if options.split is not None:
        selection_updates["split"] = options.split.value
    if options.index is not None:
        selection_updates["index"] = options.index
    if options.sample_id is not None:
        selection_updates["sample_key"] = options.sample_id
    if options.scene_id is not None:
        selection_updates["scene_id"] = options.scene_id
    if options.snippet_id is not None:
        selection_updates["snippet_id"] = options.snippet_id
    if options.rollout_context is not None:
        selection_updates["rollout_context_mode"] = options.rollout_context.value
    if selection_updates:
        cfg.selection = type(cfg.selection).model_validate({**cfg.selection.model_dump(), **selection_updates})
    if options.offline_store is not None:
        store = cfg.dataset.offline.store.model_copy(update={"store_dir": options.offline_store.expanduser()})
        offline = cfg.dataset.offline.model_copy(update={"store": store})
        cfg.dataset = cfg.dataset.model_copy(update={"offline": offline})
    if options.candidate_index is not None:
        cfg.candidate.selected_index = options.candidate_index
    if options.save_requested:
        cfg.output.mode = "save"
        if options.save_path is not None:
            cfg.output.save_path = options.save_path.expanduser()
    if options.spawn:
        cfg.output.mode = "spawn"
    if options.connect_requested:
        cfg.output.mode = "connect"
        if options.connect_addr is not None:
            cfg.output.connect_addr = options.connect_addr
    if options.view or options.serve_web:
        cfg.output.mode = "save"
    return RerunOfflineInspectorConfig.model_validate(cfg.model_dump())


def _detect_lan_ip() -> str:
    """Return the likely LAN-facing IPv4 address for user-facing hints."""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return str(sock.getsockname()[0])
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"


def _viewer_command(
    *,
    save_path: Path,
    serve_web: bool,
    lan: bool,
    web_viewer_port: int,
    ws_server_port: int,
) -> list[str]:
    """Build the foreground Rerun viewer command."""

    if not serve_web:
        return ["rerun", str(save_path)]
    return [
        "rerun",
        "--bind",
        "0.0.0.0" if lan else "127.0.0.1",
        "--serve-web",
        "--web-viewer-port",
        str(web_viewer_port),
        "--port",
        str(ws_server_port),
        str(save_path),
    ]


def _print_lan_hint(*, web_viewer_port: int) -> None:
    """Print a LAN access hint for opt-in web serving."""

    ip = _detect_lan_ip()
    if web_viewer_port > 0:
        print(f"ARIA-NBV Rerun LAN URL: http://{ip}:{web_viewer_port}/", flush=True)
    else:
        print(
            "ARIA-NBV Rerun LAN mode enabled. Rerun will choose the web-viewer port; "
            f"use host {ip} from another device.",
            flush=True,
        )


def _run_viewer_command(command: list[str], *, lan: bool, web_viewer_port: int) -> None:
    """Run Rerun in the foreground while preserving its stdout/stderr."""

    if lan:
        _print_lan_hint(web_viewer_port=web_viewer_port)
    subprocess.run(command, check=True)


class RerunOfflineInspector:
    """Own one offline-sample selection and Rerun logging session.

    :meth:`run` opens the immutable VIN reader, validates visual inventory
    before recording initialization, opens one configured sink, and then logs
    sample primitives plus provenance metadata. Runtime instances are one-shot
    orchestrators; they do not own or mutate source-store content.
    """

    def __init__(self, config: RerunOfflineInspectorConfig, *, rr_module: RerunModule | None = None) -> None:
        """Initialize the inspector runtime."""

        self.config = config
        self.rr_module = rr_module
        self.console = Console.with_prefix("nbv-rerun-inspect").set_verbosity(config.performance.verbosity)

    def run(self) -> None:
        """Select, validate, initialize, and log one immutable VIN sample.

        Required inventory failures occur before a Rerun sink is opened. Once
        started, geometry and metadata are logged as static entities for this
        single selected sample.
        """

        selected = select_rerun_sample(
            dataset_config=self.config.dataset.offline,
            selection=self.config.selection,
        )
        inventory = collect_visual_inventory(selected.sample)
        validate_required_inventory(self.config, inventory)
        logger = RerunOfflineLogger(self.config, rr_module=self.rr_module)
        logger.start()
        logger.log_sample(sample=selected.sample, inventory=inventory, selection=selected.description)
        logger.log_metadata(sample=selected.sample, inventory=inventory, selection=selected.description)
        self.console.log(
            f"Logged Rerun offline sample: {compact_ase_atek_sample_id(selected.sample.sample_key)} ({selected.description})",
        )


def run_inspector(config: RerunOfflineInspectorConfig, *, rr_module: RerunModule | None = None) -> None:
    """Create and run one offline inspector with an optional injected Rerun module.

    The injectable protocol lets tests capture session order and entities
    without spawning a viewer; production imports the installed Rerun SDK.
    """

    RerunOfflineInspector(config, rr_module=rr_module).run()


__all__ = ["RerunOfflineInspector", "app", "main", "run_inspector"]
