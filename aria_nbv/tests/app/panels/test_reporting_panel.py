"""Streamlit report preview dispatch contracts."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def _reporting_app(configs_dir) -> None:
    from aria_nbv.app.panels.reporting import render_reporting_workspace

    render_reporting_workspace(configs_dir=configs_dir)


def test_reporting_page_is_metadata_only_before_preview(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "empty.toml").write_text(
        'schema_version = "aria-nbv-report-config-v1"\nevidence_status = "pilot"\nsections = []\n',
        encoding="utf-8",
    )

    app = AppTest.from_function(
        _reporting_app,
        args=(tmp_path,),
    ).run()

    assert not app.exception
    assert app.header[0].value == "Scientific Reporting"
    assert app.info[0].value.startswith("Select Preview report")


def test_reporting_page_builds_only_after_explicit_preview(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "empty.toml").write_text(
        'schema_version = "aria-nbv-report-config-v1"\nevidence_status = "pilot"\nsections = []\n',
        encoding="utf-8",
    )
    app = AppTest.from_function(
        _reporting_app,
        args=(tmp_path,),
    ).run()

    app.button[0].click().run()

    assert not app.exception
    assert app.success[0].value.startswith("Snapshot")
