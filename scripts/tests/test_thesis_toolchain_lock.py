"""Contract tests for the thesis toolchain lock generator."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/thesis_toolchain_lock.py"
SCHEMA = ROOT / "scripts/scaffold/schemas/thesis-toolchain-lock.schema.json"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, text=True, capture_output=True
    ).stdout.strip()


@pytest.fixture
def fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    for relative in (
        "docs/typst/thesis",
        "docs/typst/shared",
        "scripts/scaffold/schemas",
        ".agents/skills/typst-authoring/scripts",
        "bin",
        "docs/figures/branding",
    ):
        (tmp_path / relative).mkdir(parents=True)
    (tmp_path / "docs/typst/thesis/main.typ").write_text(
        '#import "../shared/shared.typ"\n'
        '#show: bibliography(style: "/ieee.csl")\n'
        '#set text(font: "System Test")\n',
        encoding="utf-8",
    )
    (tmp_path / "docs/typst/shared/shared.typ").write_text(
        '#import "@preview/example:1.2.3": thing\n'
        '#let logo: "/figures/branding/hm-logo.svg"\n',
        encoding="utf-8",
    )
    (tmp_path / "docs/typst/thesis/experiment_data.typ").write_text(
        '#let report-schema-version = "report-v2"\n', encoding="utf-8"
    )
    (tmp_path / "docs/typst/thesis/figure.PNG").write_bytes(b"before")
    (tmp_path / "docs/typst/shared/diagram.svg").write_text("svg\n", encoding="utf-8")
    (tmp_path / "docs/figures/branding/hm-logo.svg").write_text(
        "logo\n", encoding="utf-8"
    )
    (tmp_path / "docs/figures/unrelated.svg").write_text(
        "unrelated\n", encoding="utf-8"
    )
    (tmp_path / "docs/ieee.csl").write_text("csl\n", encoding="utf-8")
    render = tmp_path / ".agents/skills/typst-authoring/scripts/render_png.sh"
    render.write_text("#!/bin/sh\necho render\n", encoding="utf-8")
    render.chmod(0o755)
    (tmp_path / "bin/fc-list").write_text(
        "#!/bin/sh\nprintf 'System Test|%s\\n' '$FIXTURE_FONT'\n",
        encoding="utf-8",
    )
    (tmp_path / "bin/fc-list").chmod(0o755)
    font = tmp_path / "system-test.ttf"
    font.write_bytes(b"font")
    (tmp_path / "bin/fc-list").write_text(
        f"#!/bin/sh\nprintf 'System Test|{font}\\n'\n", encoding="utf-8"
    )
    (tmp_path / "bin/fc-list").chmod(0o755)
    typst = tmp_path / "bin/typst"
    typst.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = --version ]; then echo 'typst 9.9.9 (test)'; exit; fi\n"
        'if [ "$1" = fonts ] && [ "$2" = --variants ]; then\n'
        "  echo 'System Test'; echo '- Style: Normal, Weight: 400, Stretch: FontStretch(1000)';\n"
        "  echo 'Embedded Test'; echo '- Style: Normal, Weight: 400, Stretch: FontStretch(1000)';\n"
        "  exit;\nfi\n",
        encoding="utf-8",
    )
    typst.chmod(0o755)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "fixture")
    return (
        tmp_path,
        tmp_path / "docs/typst/thesis/toolchain-lock.json",
        _git(tmp_path, "rev-parse", "HEAD"),
    )


def _run(
    root: Path, output: Path, mode: str, *extra: str
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": f"{root / 'bin'}:{os.environ['PATH']}"}
    return subprocess.run(
        [
            "python3",
            str(SCRIPT),
            mode,
            "--root",
            str(root),
            "--output",
            str(output),
            *extra,
        ],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def _generate(root: Path, output: Path, revision: str) -> dict[str, Any]:
    result = _run(root, output, "generate", "--source-revision", revision)
    assert result.returncode == 0, result.stderr
    return cast(dict[str, Any], json.loads(output.read_text()))


def test_generation_records_closure_and_path_independent_identities(fixture) -> None:
    root, output, revision = fixture
    payload = _generate(root, output, revision)
    paths = {entry["path"] for entry in payload["material_sources"]}
    assert "docs/typst/thesis/main.typ" in paths
    assert "docs/typst/shared/shared.typ" in paths
    assert "docs/figures/branding/hm-logo.svg" in paths
    assert "docs/typst/thesis/figure.PNG" not in paths
    assert "docs/typst/shared/diagram.svg" not in paths
    assert "docs/figures/unrelated.svg" not in paths
    assert payload["toolchain"]["compiler"]["command"] == "typst"
    assert "executable" not in payload["toolchain"]["compiler"]
    assert len(payload["toolchain"]["compiler"]["binary_sha256"]) == 64
    font = payload["toolchain"]["fonts"][0]
    assert font["source"] == "system"
    assert font["system_files"][0]["basename"] == "system-test.ttf"


def test_exact_generated_outputs_are_excluded_but_other_assets_are_material(
    fixture,
) -> None:
    root, output, revision = fixture
    for relative in (
        "docs/typst/thesis/main.pdf",
        "docs/typst/thesis/toolchain-lock.json",
        "docs/typst/thesis/release-requirements.toml",
    ):
        (root / relative).write_bytes(b"generated")
    payload = _generate(root, output, revision)
    paths = {entry["path"] for entry in payload["material_sources"]}
    assert not paths.intersection(
        {
            "docs/typst/thesis/main.pdf",
            "docs/typst/thesis/toolchain-lock.json",
            "docs/typst/thesis/release-requirements.toml",
        }
    )


def test_referenced_asset_byte_drift_fails(fixture) -> None:
    root, output, revision = fixture
    _generate(root, output, revision)
    (root / "docs/figures/branding/hm-logo.svg").write_bytes(b"after")
    failed = _run(root, output, "check")
    assert failed.returncode == 1
    assert "material build inputs" in failed.stderr


def test_untracked_unreferenced_visual_does_not_fail(fixture) -> None:
    root, output, revision = fixture
    _generate(root, output, revision)
    (root / "docs/figures/new.jpg").write_bytes(b"new")
    passed = _run(root, output, "check")
    assert passed.returncode == 0, passed.stderr


def test_missing_font_and_fallback_family_are_rejected(fixture) -> None:
    root, output, _revision = fixture
    source = root / "docs/typst/thesis/main.typ"
    source.write_text(source.read_text().replace("System Test", "Missing Test"))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "missing font")
    failed = _run(
        root, output, "generate", "--source-revision", _git(root, "rev-parse", "HEAD")
    )
    assert failed.returncode == 1
    assert "absent from Typst resolver" in failed.stderr

    source.write_text(source.read_text().replace("Missing Test", "Embedded Test"))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "embedded font")
    payload = _generate(root, output, _git(root, "rev-parse", "HEAD"))
    embedded = next(
        font
        for font in payload["toolchain"]["fonts"]
        if font["family"] == "Embedded Test"
    )
    assert embedded["source"] == "embedded_in_compiler"
    assert "Noto Sans" not in json.dumps(embedded)
    assert (
        embedded["compiler_binding"]["binary_sha256"]
        == payload["toolchain"]["compiler"]["binary_sha256"]
    )


def test_binary_drift_is_detected_by_hash(fixture) -> None:
    root, output, revision = fixture
    _generate(root, output, revision)
    typst = root / "bin/typst"
    typst.write_text(typst.read_text() + "# drift\n")
    failed = _run(root, output, "check")
    assert failed.returncode == 1
    assert "lock drift detected" in failed.stderr


def test_schema_is_strict_and_compiler_identity_is_portable() -> None:
    schema = json.loads(SCHEMA.read_text())
    compiler = schema["properties"]["toolchain"]["properties"]["compiler"]
    assert compiler["required"] == ["command", "version", "binary_sha256"]
    assert "executable" not in compiler["properties"]
