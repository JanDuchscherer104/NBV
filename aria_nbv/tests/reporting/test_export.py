"""Atomic, source-independent report export tests."""

from __future__ import annotations

import json
from pathlib import Path

from plotly import graph_objects as go

from aria_nbv.reporting import (
    ReportFigure,
    ReportSnapshot,
    ScientificReportError,
    SourceIdentity,
    write_report_snapshot,
)
from aria_nbv.reporting.results import canonical_plotly_json


class _Renderer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

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
        self.calls += 1
        if self.fail:
            raise RuntimeError("render failed")
        destination.write_bytes(f"{image_format}:{width}:{height}:{scale}".encode() + plotly_json)

    def fingerprint(self) -> dict[str, str]:
        return {"renderer": "fixture-v1"}


def _snapshot() -> ReportSnapshot:
    source = SourceIdentity("source", "wandb", "a" * 64, (("run_count", 1),))
    figure = ReportFigure(
        id="curve",
        plotly_json=canonical_plotly_json(go.Figure(go.Scatter(x=[0, 1], y=[1, 0]))),
        source_ids=("source",),
        source_result_ids=(),
        symbol_ids=(),
        uses_webgl=False,
    )
    return ReportSnapshot.create(
        evidence_status="pilot",
        config_sha256="b" * 64,
        notation_sha256="c" * 64,
        source_identities=(source,),
        quantities=(),
        tables=(),
        figures=(figure,),
        resolved_recipe=b'schema_version = "aria-nbv-report-config-v1"\n',
    )


def test_export_writes_exact_plotly_json_and_manifest(tmp_path: Path) -> None:
    destination = tmp_path / "report"
    renderer = _Renderer()

    receipt = write_report_snapshot(_snapshot(), destination, renderer=renderer)

    report = json.loads((destination / "report.json").read_text())
    plotly_path = destination / report["figures"][0]["plotly_path"]
    assert plotly_path.read_bytes() == _snapshot().figures[0].plotly_json
    assert receipt.destination == destination
    assert renderer.calls == 1

    cached = write_report_snapshot(_snapshot(), destination, renderer=renderer)

    assert cached.manifest_sha256 == receipt.manifest_sha256
    assert renderer.calls == 1


def test_failed_render_preserves_previous_publication(tmp_path: Path) -> None:
    destination = tmp_path / "report"
    destination.mkdir()
    (destination / "sentinel.txt").write_text("previous", encoding="utf-8")

    try:
        write_report_snapshot(_snapshot(), destination, renderer=_Renderer(fail=True))
    except Exception:
        pass

    assert (destination / "sentinel.txt").read_text(encoding="utf-8") == "previous"


def test_webgl_uses_png_and_remote_resources_fail_closed(tmp_path: Path) -> None:
    source = SourceIdentity("source", "wandb", "a" * 64, (("run_count", 1),))
    webgl = ReportFigure(
        id="surface",
        plotly_json=canonical_plotly_json(go.Figure(go.Surface(z=[[0, 1], [1, 0]]))),
        source_ids=("source",),
        source_result_ids=(),
        symbol_ids=(),
        uses_webgl=True,
    )
    snapshot = ReportSnapshot.create(
        evidence_status="pilot",
        config_sha256="b" * 64,
        notation_sha256="c" * 64,
        source_identities=(source,),
        quantities=(),
        tables=(),
        figures=(webgl,),
        resolved_recipe=b"",
    )
    renderer = _Renderer()

    write_report_snapshot(snapshot, tmp_path / "webgl", renderer=renderer)

    report = json.loads((tmp_path / "webgl" / "report.json").read_text())
    assert report["figures"][0]["static_path"].endswith(".png")

    remote = ReportFigure(
        id="remote",
        plotly_json=canonical_plotly_json(
            go.Figure(layout={"images": [{"source": "https://example.invalid/image.png"}]})
        ),
        source_ids=("source",),
        source_result_ids=(),
        symbol_ids=(),
        uses_webgl=False,
    )
    remote_snapshot = ReportSnapshot.create(
        evidence_status="pilot",
        config_sha256="b" * 64,
        notation_sha256="c" * 64,
        source_identities=(source,),
        quantities=(),
        tables=(),
        figures=(remote,),
        resolved_recipe=b"",
    )

    try:
        write_report_snapshot(remote_snapshot, tmp_path / "remote", renderer=renderer)
    except ScientificReportError as exc:
        assert exc.code == "render_failed"
    else:
        raise AssertionError("remote Plotly resources must fail closed")
