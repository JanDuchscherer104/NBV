"""Contract tests for the thesis toolchain lock generator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

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
    (tmp_path / "docs/typst/thesis").mkdir(parents=True)
    (tmp_path / "docs/typst/shared").mkdir(parents=True)
    (tmp_path / "scripts/scaffold/schemas").mkdir(parents=True)
    (tmp_path / ".agents/skills/typst-authoring/scripts").mkdir(parents=True)
    (tmp_path / "docs/typst/thesis/main.typ").write_text(
        '#import "../shared/shared.typ"\n#show: bibliography(style: "/ieee.csl")\n#set text(font: "DejaVu Sans")\n',
        encoding="utf-8",
    )
    (tmp_path / "docs/typst/shared/shared.typ").write_text(
        '#import "@preview/example:1.2.3": thing\n', encoding="utf-8"
    )
    (tmp_path / "docs/typst/thesis/experiment_data.typ").write_text(
        '#let report-schema-version = "report-v2"\n', encoding="utf-8"
    )
    (tmp_path / "docs/ieee.csl").parent.mkdir(exist_ok=True)
    (tmp_path / "docs/ieee.csl").write_text("csl\n", encoding="utf-8")
    render = tmp_path / ".agents/skills/typst-authoring/scripts/render_png.sh"
    render.write_text("#!/bin/sh\necho render\n", encoding="utf-8")
    render.chmod(0o755)
    typst = tmp_path / "typst"
    typst.write_text(
        "#!/bin/sh\n[ \"$1\" = --version ] && echo 'typst 9.9.9 (test)'\n",
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
    env = {**os.environ, "PATH": f"{root}:{os.environ['PATH']}"}
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
        text=True,
        capture_output=True,
        env=env,
    )


def test_clean_generation_and_check_records_all_identities(
    fixture: tuple[Path, Path, str],
) -> None:
    root, output, revision = fixture
    generated = _run(root, output, "generate", "--source-revision", revision)
    assert generated.returncode == 0, generated.stderr
    payload = json.loads(output.read_text())
    assert payload["source_revision"] == revision
    assert payload["toolchain"]["compiler"]["executable"] == str(
        (root / "typst").resolve()
    )
    assert payload["toolchain"]["packages"] == [{"identity": "@preview/example:1.2.3"}]
    assert payload["toolchain"]["csl"]["path"] == "docs/ieee.csl"
    assert payload["toolchain"]["rasterizer"]["ppi"] == 300
    assert payload["report_schema_version"] == "report-v2"
    checked = _run(root, output, "check")
    assert checked.returncode == 0, checked.stderr


def test_material_drift_and_schema_failure_are_reported(
    fixture: tuple[Path, Path, str],
) -> None:
    root, output, revision = fixture
    assert _run(root, output, "generate", "--source-revision", revision).returncode == 0
    source = root / "docs/typst/thesis/main.typ"
    source.write_text(source.read_text() + "drift\n")
    failed = _run(root, output, "check")
    assert failed.returncode == 1
    assert "material build inputs" in failed.stderr
    output.write_text(json.dumps({"schema_version": "bad"}))
    failed = _run(root, output, "check")
    assert failed.returncode == 1
    assert "missing required fields" in failed.stderr


def test_alternate_compiler_identity_is_rejected(
    fixture: tuple[Path, Path, str],
) -> None:
    root, output, revision = fixture
    assert _run(root, output, "generate", "--source-revision", revision).returncode == 0
    failed = _run(root, output, "check", "--typst-bin", "alternate-typst")
    assert failed.returncode == 1
    assert "command failed" in failed.stderr


def test_ledger_only_audit_commit_does_not_change_recorded_material_revision(
    fixture: tuple[Path, Path, str],
) -> None:
    root, output, revision = fixture
    assert _run(root, output, "generate", "--source-revision", revision).returncode == 0
    lock_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    ledger = root / "docs/typst/thesis/release-requirements.toml"
    ledger.write_text(
        f'lock_path = "docs/typst/thesis/toolchain-lock.json"\nlock_sha256 = "{lock_hash}"\n'
    )
    _git(
        root,
        "add",
        output.relative_to(root).as_posix(),
        ledger.relative_to(root).as_posix(),
    )
    _git(root, "commit", "-qm", "release ledger audit")
    checked = _run(root, output, "check")
    assert checked.returncode == 0, checked.stderr
    material = {
        entry["path"] for entry in json.loads(output.read_text())["material_sources"]
    }
    assert "docs/typst/thesis/toolchain-lock.json" not in material
    assert "docs/typst/thesis/release-requirements.toml" not in material


@pytest.mark.parametrize(
    "relative",
    (
        "docs/typst/thesis/untracked.typ",
        "docs/typst/shared/untracked.typ",
        "docs/untracked.bib",
        "docs/untracked.csl",
    ),
)
def test_untracked_material_input_is_rejected(
    fixture: tuple[Path, Path, str], relative: str
) -> None:
    root, output, revision = fixture
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("untracked\n")
    failed = _run(root, output, "generate", "--source-revision", revision)
    assert failed.returncode == 1
    assert f"untracked material thesis inputs: {relative}" in failed.stderr


def test_deleted_tracked_material_input_is_rejected(
    fixture: tuple[Path, Path, str],
) -> None:
    root, output, revision = fixture
    (root / "docs/typst/shared/shared.typ").unlink()
    failed = _run(root, output, "generate", "--source-revision", revision)
    assert failed.returncode == 1
    assert (
        "material thesis input is missing: docs/typst/shared/shared.typ"
        in failed.stderr
    )


def test_schema_valid_lock_drift_is_rejected(fixture: tuple[Path, Path, str]) -> None:
    root, output, revision = fixture
    assert _run(root, output, "generate", "--source-revision", revision).returncode == 0
    payload = json.loads(output.read_text())
    payload["build_commands"]["development"] += " --input audit=true"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    failed = _run(root, output, "check")
    assert failed.returncode == 1
    assert "lock drift detected" in failed.stderr


def test_builtin_ieee_selection_fails_clearly(fixture: tuple[Path, Path, str]) -> None:
    root, output, revision = fixture
    source = root / "docs/typst/thesis/main.typ"
    source.write_text(source.read_text().replace('style: "/ieee.csl"', 'style: "ieee"'))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "builtin")
    failed = _run(
        root, output, "generate", "--source-revision", _git(root, "rev-parse", "HEAD")
    )
    assert failed.returncode == 1
    assert "no tracked CSL path selected" in failed.stderr


def test_schema_is_strict() -> None:
    schema = json.loads(SCHEMA.read_text())
    assert schema["additionalProperties"] is False
    assert "material_sources" in schema["required"]
