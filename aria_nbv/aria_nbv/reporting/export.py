"""Deterministic staged export of already materialized report snapshots.

The exporter never accepts a report config and never owns evidence adapters.
It serializes the exact quantities, tables, and canonical Plotly JSON present
in a :class:`ReportSnapshot`, renders static assets, validates digests, then
atomically promotes the complete directory for Typst consumption.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import locale
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from .errors import ScientificReportError
from .results import ReportSnapshot


@dataclass(frozen=True, slots=True)
class _RenderRequest:
    plotly_json: bytes
    destination: Path
    image_format: str
    width: int
    height: int
    scale: float
    result_id: str


class _StaticRenderer(Protocol):
    def render(
        self,
        plotly_json: bytes,
        destination: Path,
        *,
        image_format: str,
        width: int,
        height: int,
        scale: float,
    ) -> None:
        """Render one canonical Plotly specification to a static asset."""

    def fingerprint(self) -> dict[str, str]:
        """Return dependency and host fields that influence rendered bytes."""


class _KaleidoRenderer:
    """Plotly/Kaleido renderer used by the production exporter."""

    def render(
        self,
        plotly_json: bytes,
        destination: Path,
        *,
        image_format: str,
        width: int,
        height: int,
        scale: float,
    ) -> None:
        import plotly.io as pio

        figure = pio.from_json(plotly_json.decode("utf-8"), output_type="Figure", skip_invalid=False)
        pio.write_image(figure, destination, format=image_format, width=width, height=height, scale=scale)

    def render_many(self, requests: tuple[_RenderRequest, ...]) -> None:
        """Render a homogeneous-size batch in one Kaleido transaction."""

        if not requests:
            return
        import plotly.io as pio

        figures = [
            pio.from_json(request.plotly_json.decode("utf-8"), output_type="Figure", skip_invalid=False)
            for request in requests
        ]
        pio.write_images(
            fig=figures,
            file=[request.destination for request in requests],
            width=requests[0].width,
            height=requests[0].height,
            scale=requests[0].scale,
        )

    def fingerprint(self) -> dict[str, str]:
        import plotly.io as pio

        browser_path, browser_version = _browser_identity()
        return {
            "plotly": _package_version("plotly"),
            "kaleido": _package_version("kaleido"),
            "browser_path": browser_path,
            "browser_version": browser_version,
            "mathjax": str(pio.defaults.mathjax or "plotly-default"),
            "plotlyjs": str(pio.defaults.plotlyjs or "plotly-bundled"),
            "topojson": str(pio.defaults.topojson or "plotly-default"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "locale": ".".join(part for part in locale.getlocale() if part) or "unknown",
            "timezone": os.environ.get("TZ", "system"),
        }


@dataclass(frozen=True, slots=True)
class ReportWriteReceipt:
    """Identity of one atomically published report directory."""

    destination: Path
    """Absolute promoted report directory."""

    manifest_sha256: str
    """Digest of the exact exported manifest bytes."""

    snapshot_sha256: str
    """Digest of the immutable input snapshot."""

    assets: tuple[tuple[str, str], ...]
    """Sorted relative asset path and SHA-256 pairs."""


def write_report_snapshot(
    snapshot: ReportSnapshot,
    destination: Path,
    *,
    width: int = 1400,
    height: int = 900,
    scale: float = 2.0,
    two_dimensional_format: str = "svg",
    webgl_format: str = "png",
    renderer: _StaticRenderer | None = None,
) -> ReportWriteReceipt:
    """Atomically export the exact supplied snapshot without source access.

    Ordinary 2D figures use SVG by default. WebGL/3D figures use high-
    resolution PNG because vector containers rasterize their WebGL layers.
    A render or validation failure removes only the staging directory and keeps
    the previously published destination intact.
    """

    target = destination.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    active_renderer = renderer or _KaleidoRenderer()
    if two_dimensional_format not in {"svg", "png"} or webgl_format != "png":
        raise ScientificReportError("export_failed", "Unsupported static report image format.")
    if width < 1 or height < 1 or scale <= 0:
        raise ScientificReportError("export_failed", "Report render dimensions and scale must be positive.")
    renderer_fingerprint = dict(sorted(active_renderer.fingerprint().items()))
    render_settings = _render_settings(
        snapshot,
        width=width,
        height=height,
        scale=scale,
        two_dimensional_format=two_dimensional_format,
        webgl_format=webgl_format,
    )
    existing = _existing_receipt(
        target,
        snapshot=snapshot,
        renderer_fingerprint=renderer_fingerprint,
        render_settings=render_settings,
    )
    if existing is not None:
        return existing
    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=target.parent))
    backup: Path | None = None
    try:
        receipt = _write_stage(
            snapshot,
            stage,
            renderer=active_renderer,
            width=width,
            height=height,
            scale=scale,
            two_dimensional_format=two_dimensional_format,
            webgl_format=webgl_format,
            renderer_fingerprint=renderer_fingerprint,
            render_settings=render_settings,
        )
        if target.exists():
            backup = target.with_name(f".{target.name}.previous-{snapshot.snapshot_sha256[:12]}")
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except Exception:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
            raise
        if backup is not None:
            shutil.rmtree(backup)
        return ReportWriteReceipt(
            destination=target,
            manifest_sha256=receipt.manifest_sha256,
            snapshot_sha256=receipt.snapshot_sha256,
            assets=receipt.assets,
        )
    except ScientificReportError:
        raise
    except Exception as exc:
        raise ScientificReportError("export_failed", f"Could not export report snapshot: {exc}") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _write_stage(
    snapshot: ReportSnapshot,
    stage: Path,
    *,
    renderer: _StaticRenderer,
    width: int,
    height: int,
    scale: float,
    two_dimensional_format: str,
    webgl_format: str,
    renderer_fingerprint: dict[str, str],
    render_settings: dict[str, object],
) -> ReportWriteReceipt:
    figures_dir = stage / "figures"
    assets_dir = stage / "assets"
    figures_dir.mkdir()
    assets_dir.mkdir()
    (stage / "recipe.toml").write_bytes(snapshot.resolved_recipe)
    asset_digests: dict[str, str] = {}
    figure_rows: list[dict[str, object]] = []
    render_requests: list[_RenderRequest] = []
    for figure in snapshot.figures:
        _reject_remote_resources(figure.plotly_json, result_id=figure.id)
        plotly_path = figures_dir / f"{figure.id}.{_sha256(figure.plotly_json)[:16]}.plotly.json"
        plotly_path.write_bytes(figure.plotly_json)
        asset_digests[plotly_path.relative_to(stage).as_posix()] = _sha256(plotly_path.read_bytes())
        image_format = webgl_format if figure.uses_webgl else two_dimensional_format
        asset_path = assets_dir / f"{figure.id}.{_sha256(figure.plotly_json)[:16]}.{image_format}"
        render_requests.append(
            _RenderRequest(
                plotly_json=figure.plotly_json,
                destination=asset_path,
                image_format=image_format,
                width=width,
                height=height,
                scale=scale,
                result_id=figure.id,
            )
        )
        figure_rows.append(
            {
                "id": figure.id,
                "plotly_path": plotly_path.relative_to(stage).as_posix(),
                "static_path": asset_path.relative_to(stage).as_posix(),
                "uses_webgl": figure.uses_webgl,
                "symbol_ids": list(figure.symbol_ids),
                "source_ids": list(figure.source_ids),
                "source_result_ids": list(figure.source_result_ids),
            }
        )
    batch_render = getattr(renderer, "render_many", None)
    if callable(batch_render):
        try:
            batch_render(tuple(render_requests))
        except Exception as exc:
            raise ScientificReportError("render_failed", str(exc)) from exc
    else:
        for request in render_requests:
            try:
                renderer.render(
                    request.plotly_json,
                    request.destination,
                    image_format=request.image_format,
                    width=request.width,
                    height=request.height,
                    scale=request.scale,
                )
            except Exception as exc:
                raise ScientificReportError("render_failed", str(exc), result_id=request.result_id) from exc
    for request in render_requests:
        if not request.destination.is_file() or request.destination.stat().st_size == 0:
            raise ScientificReportError(
                "render_failed",
                "Renderer produced no asset bytes.",
                result_id=request.result_id,
            )
        asset_digests[request.destination.relative_to(stage).as_posix()] = _sha256(request.destination.read_bytes())
    report_payload = {
        "schema_version": "aria-nbv-report-bundle-v2",
        "evidence_status": snapshot.evidence_status,
        "snapshot_sha256": snapshot.snapshot_sha256,
        "config_sha256": snapshot.config_sha256,
        "notation_sha256": snapshot.notation_sha256,
        "sources": [asdict(source) for source in snapshot.source_identities],
        "quantities": [asdict(quantity) for quantity in snapshot.quantities],
        "tables": [asdict(table) for table in snapshot.tables],
        "figures": figure_rows,
    }
    report_bytes = _canonical_json(report_payload)
    (stage / "report.json").write_bytes(report_bytes)
    asset_digests["recipe.toml"] = _sha256(snapshot.resolved_recipe)
    asset_digests["report.json"] = _sha256(report_bytes)
    manifest_payload = {
        "schema_version": "aria-nbv-report-manifest-v1",
        "snapshot_sha256": snapshot.snapshot_sha256,
        "assets": dict(sorted(asset_digests.items())),
        "renderer": renderer_fingerprint,
        "render_settings": render_settings,
    }
    manifest_bytes = _canonical_json(manifest_payload)
    (stage / "manifest.json").write_bytes(manifest_bytes)
    return ReportWriteReceipt(
        destination=stage,
        manifest_sha256=_sha256(manifest_bytes),
        snapshot_sha256=snapshot.snapshot_sha256,
        assets=tuple(sorted(asset_digests.items())),
    )


def _canonical_json(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _render_settings(
    snapshot: ReportSnapshot,
    *,
    width: int,
    height: int,
    scale: float,
    two_dimensional_format: str,
    webgl_format: str,
) -> dict[str, object]:
    fonts: set[str] = set()
    template_digests: set[str] = set()
    for figure in snapshot.figures:
        payload = json.loads(figure.plotly_json)
        layout = payload.get("layout", {}) if isinstance(payload, dict) else {}
        if not isinstance(layout, dict):
            continue
        font = layout.get("font", {})
        if isinstance(font, dict) and isinstance(font.get("family"), str):
            fonts.add(font["family"])
        if "template" in layout:
            template_digests.add(_sha256(_canonical_json(layout["template"])))
    return {
        "width": width,
        "height": height,
        "scale": scale,
        "two_dimensional_format": two_dimensional_format,
        "webgl_format": webgl_format,
        "font_families": sorted(fonts),
        "font_fingerprints": [_font_identity(family) for family in sorted(fonts)],
        "template_sha256": sorted(template_digests),
    }


def _existing_receipt(
    target: Path,
    *,
    snapshot: ReportSnapshot,
    renderer_fingerprint: dict[str, str],
    render_settings: dict[str, object],
) -> ReportWriteReceipt | None:
    manifest_path = target / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (
        manifest.get("snapshot_sha256") != snapshot.snapshot_sha256
        or manifest.get("renderer") != renderer_fingerprint
        or manifest.get("render_settings") != render_settings
    ):
        return None
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        return None
    validated: list[tuple[str, str]] = []
    for relative_path, digest in sorted(assets.items()):
        if not isinstance(relative_path, str) or not isinstance(digest, str):
            return None
        asset_path = target / relative_path
        try:
            observed = _sha256(asset_path.read_bytes())
        except OSError:
            return None
        if observed != digest:
            return None
        validated.append((relative_path, digest))
    return ReportWriteReceipt(
        destination=target,
        manifest_sha256=_sha256(manifest_bytes),
        snapshot_sha256=snapshot.snapshot_sha256,
        assets=tuple(validated),
    )


def _reject_remote_resources(plotly_json: bytes, *, result_id: str) -> None:
    payload = json.loads(plotly_json)

    def visit(value: object) -> bool:
        if isinstance(value, str):
            return value.lower().startswith(("http://", "https://"))
        if isinstance(value, dict):
            return any(visit(item) for item in value.values())
        if isinstance(value, list):
            return any(visit(item) for item in value)
        return False

    if visit(payload):
        raise ScientificReportError(
            "render_failed",
            "Canonical Plotly specifications may not reference remote resources.",
            result_id=result_id,
        )


def _browser_identity() -> tuple[str, str]:
    for executable in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(executable)
        if path is None:
            continue
        try:
            completed = subprocess.run(
                [path, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            version = completed.stdout.strip() or completed.stderr.strip() or "unknown"
        except (OSError, subprocess.SubprocessError):
            version = "unknown"
        return path, version
    return "unavailable", "unavailable"


def _font_identity(family: str) -> dict[str, str]:
    executable = shutil.which("fc-match")
    if executable is None:
        return {"requested_family": family, "resolved": "unavailable", "sha256": "unavailable"}
    try:
        completed = subprocess.run(
            [executable, "--format", "%{file}\n%{family}\n%{style}\n", family],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
        lines = completed.stdout.splitlines()
        font_path = Path(lines[0]) if lines else Path()
        digest = _sha256(font_path.read_bytes()) if font_path.is_file() else "unavailable"
        resolved = " | ".join(lines[1:3]) if len(lines) >= 3 else completed.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        digest = "unavailable"
        resolved = "unavailable"
    return {"requested_family": family, "resolved": resolved, "sha256": digest}


__all__ = ["ReportWriteReceipt", "write_report_snapshot"]
