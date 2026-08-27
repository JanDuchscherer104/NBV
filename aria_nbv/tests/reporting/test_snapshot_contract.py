"""Contract tests for immutable scientific report snapshots."""

from __future__ import annotations

import json

import pytest
from plotly import graph_objects as go

from aria_nbv.reporting import NamedQuantity, ReportFigure, ReportSnapshot, ScientificReportConfig, SourceIdentity
from aria_nbv.reporting.config import ReportSourcesConfig, WandbReportSectionConfig, WandbSourceConfig
from aria_nbv.reporting.results import canonical_plotly_json


def _source() -> SourceIdentity:
    return SourceIdentity(
        id="source",
        kind="wandb",
        sha256="a" * 64,
        provenance=(("run_count", 1),),
    )


def test_snapshot_canonicalizes_result_order_and_seals_contents() -> None:
    figure = go.Figure(go.Scatter(x=[0, 1], y=[1, 2], uid="generated"))
    snapshot = ReportSnapshot.create(
        evidence_status="pilot",
        config_sha256="b" * 64,
        notation_sha256="c" * 64,
        source_identities=(_source(),),
        quantities=(
            NamedQuantity("z", 2.0, None, 1, "last", ("source",), None),
            NamedQuantity("a", 1.0, None, 1, "last", ("source",), None),
        ),
        tables=(),
        figures=(
            ReportFigure(
                id="figure",
                plotly_json=canonical_plotly_json(figure),
                source_ids=("source",),
                source_result_ids=("a",),
                symbol_ids=(),
                uses_webgl=False,
            ),
        ),
        resolved_recipe=b'schema_version = "aria-nbv-report-config-v1"\n',
    )

    assert tuple(quantity.id for quantity in snapshot.quantities) == ("a", "z")
    assert len(snapshot.snapshot_sha256) == 64
    assert "uid" not in json.loads(snapshot.figures[0].plotly_json)["data"][0]


def test_nonfinite_quantity_fails_closed() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        NamedQuantity("bad", float("nan"), None, 1, "mean", ("source",), None)


def test_unknown_result_provenance_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        ReportSnapshot.create(
            evidence_status="pilot",
            config_sha256="b" * 64,
            notation_sha256="c" * 64,
            source_identities=(_source(),),
            quantities=(NamedQuantity("bad", 1, None, 1, "count", ("missing",), None),),
            tables=(),
            figures=(),
            resolved_recipe=b"",
        )


def test_incomplete_external_selectors_fail_before_client_construction() -> None:
    recipe = ScientificReportConfig(
        sources=ReportSourcesConfig(wandb=WandbSourceConfig(project="project")),
        sections=(WandbReportSectionConfig(metric="val/loss"),),
    )

    with pytest.raises(Exception, match="entity, project, and exact run IDs"):
        recipe.validate_build_readiness()
