"""Command-line composition for metadata-only report recipes."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aria_nbv.reporting.cli import app


def test_cli_builds_and_exports_one_validated_recipe(tmp_path: Path) -> None:
    recipe = tmp_path / "report.toml"
    recipe.write_text(
        "\n".join(
            (
                'schema_version = "aria-nbv-report-config-v1"',
                'evidence_status = "pilot"',
                "sections = []",
                "",
            )
        ),
        encoding="utf-8",
    )
    output = tmp_path / "bundle"

    result = CliRunner().invoke(app, ["build", "--config", str(recipe), "--output", str(output)])

    assert result.exit_code == 0, result.output
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "aria-nbv-report-bundle-v2"
    assert report["figures"] == []
    assert (output / "manifest.json").is_file()
