"""Regression tests for the G006 thesis release gates."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "thesis_release", ROOT / "scripts/thesis_release.py"
)
assert SPEC and SPEC.loader
RELEASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RELEASE)


def test_audit_accepts_documented_pending_lock_without_submission_claim() -> None:
    data = RELEASE.load_release_requirements()
    RELEASE.validate_release_requirements(data)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data["requirements"][0].pop("source_urls"),
        lambda data: data["requirements"][0].update(classification="made_up"),
        lambda data: data["submission"].update(primuss_state="submitted"),
        lambda data: data["declaration"].update(presence=""),
        lambda data: data["ai_disclosure"].update(presence="missing"),
    ],
)
def test_provenance_and_external_submission_claims_are_rejected(mutation) -> None:
    data = copy.deepcopy(RELEASE.load_release_requirements())
    mutation(data)
    with pytest.raises(RELEASE.ReleaseRequirementsError):
        RELEASE.validate_release_requirements(data)


def test_final_lock_is_required_and_its_sha256_is_verified(tmp_path: Path) -> None:
    data = RELEASE.load_release_requirements()
    with pytest.raises(
        RELEASE.ReleaseRequirementsError, match="generated toolchain lock"
    ):
        RELEASE.validate_release_requirements(data, final=True, lock_root=tmp_path)
    lock_path = tmp_path / RELEASE.LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert revision != RELEASE._git_revision(ROOT)
    lock_path.write_text(json.dumps({"source_revision": revision}), encoding="utf-8")
    data["toolchain_lock"].update(
        sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        sha256_state="verified",
    )
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="full schema"):
        RELEASE.validate_release_requirements(data, lock_root=tmp_path)
    lock_path.write_text("drift\n", encoding="utf-8")
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="SHA-256"):
        RELEASE.validate_release_requirements(data, lock_root=tmp_path)


def test_later_ledger_lock_only_audit_commit_keeps_material_lock_revision(
    tmp_path: Path,
) -> None:
    data = RELEASE.load_release_requirements()
    lock_path = tmp_path / RELEASE.LOCK_RELATIVE_PATH
    lock_path.parent.mkdir(parents=True)
    material_revision = subprocess.run(
        ["git", "rev-parse", "HEAD^"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    lock_path.write_text(
        json.dumps({"source_revision": material_revision}), encoding="utf-8"
    )
    data["toolchain_lock"].update(
        sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        sha256_state="verified",
    )
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="full schema"):
        RELEASE.validate_release_requirements(data, final=True, lock_root=tmp_path)


def test_real_claims_are_withheld_and_cannot_be_promoted() -> None:
    model = RELEASE._claims_model(ROOT)
    with pytest.raises(
        RELEASE.ReleaseRequirementsError, match="real claims/evidence are withheld"
    ):
        RELEASE.validate_confirmatory_claims(model)
    assert all(claim.release_state == "withheld" for claim in model.claims)


def test_accepted_claim_boundary_is_compositional_without_mutating_registry() -> None:
    accepted = SimpleNamespace(
        claims=(
            SimpleNamespace(
                id="mock-accepted",
                maturity="confirmatory",
                review_state="approved",
                release_state="admissible",
            ),
        )
    )
    RELEASE.validate_confirmatory_claims(accepted)


def test_report_rejects_fixture_notice_and_provenance_mismatch(tmp_path: Path) -> None:
    payload = {
        "schema_version": "aria-nbv-thesis-report-v2",
        "bundle_role": "evidence",
        "fixture_notice": "test fixture only",
        "source_revision": "a" * 40,
        "tables": {
            "empirical_results": {
                "rows": [{"status": "confirmatory", "source_revision": "b" * 40}]
            }
        },
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="fixture_notice"):
        RELEASE.load_report(report, "a" * 40)
    payload.pop("fixture_notice")
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="matching provenance"):
        RELEASE.load_report(report, "a" * 40)


def test_report_rejects_relabelled_canonical_fixture_with_matching_revision(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (ROOT / "docs/typst/thesis/data/report-bundle-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    payload.pop("fixture_notice")
    payload["bundle_role"] = "evidence"
    payload["source_revision"] = "a" * 40
    for table in payload["tables"].values():
        for row in table["rows"]:
            if "status" in row:
                row["status"] = "confirmatory"
            if "source_revision" in row:
                row["source_revision"] = "a" * 40
    report = tmp_path / "relabelled-fixture.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        RELEASE.ReleaseRequirementsError, match="serialized evidence bundle"
    ):
        RELEASE.load_report(report, "a" * 40)


def test_report_rejects_nonhex_or_mismatched_source_revision(tmp_path: Path) -> None:
    payload = {
        "schema_version": "aria-nbv-thesis-report-v2",
        "bundle_role": "evidence",
        "source_revision": "z" * 40,
        "tables": {
            "empirical_results": {
                "rows": [{"status": "confirmatory", "source_revision": "z" * 40}]
            }
        },
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="source_revision"):
        RELEASE.load_report(report, "a" * 40)


def test_report_rejects_non_object_empirical_row(tmp_path: Path) -> None:
    payload = {
        "schema_version": "aria-nbv-thesis-report-v2",
        "bundle_role": "evidence",
        "source_revision": "a" * 40,
        "tables": {"empirical_results": {"rows": [None]}},
    }
    report = tmp_path / "report.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(
        RELEASE.ReleaseRequirementsError, match="confirmatory empirical results"
    ):
        RELEASE.load_report(report, "a" * 40)


def test_submission_checks_full_toolchain_lock_before_typst(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        RELEASE,
        "validate_release_requirements",
        lambda *args, **kwargs: {"source_revision": "a" * 40},
    )
    monkeypatch.setattr(RELEASE, "validate_confirmatory_claims", lambda _model: None)
    monkeypatch.setattr(RELEASE, "_claims_model", lambda _root: object())
    monkeypatch.setattr(RELEASE, "load_report", lambda _path, _revision: {})

    def fake_run(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command, stderr="lock drift")

    monkeypatch.setattr(RELEASE.subprocess, "run", fake_run)
    with pytest.raises(
        RELEASE.ReleaseRequirementsError, match="Typst submission compile"
    ):
        RELEASE.build_submission(
            root=ROOT,
            report=ROOT / "docs/typst/thesis/data/report-bundle-fixture.json",
            output=tmp_path / "submission.pdf",
            typst_bin="alternate-typst",
        )
    assert len(calls) == 1
    assert calls[0][1].endswith("scripts/thesis_toolchain_lock.py")
    assert calls[0][2] == "check"
    assert "--root" in calls[0] and str(ROOT) in calls[0]
    assert "--output" in calls[0]
    assert "--typst-bin" in calls[0] and "alternate-typst" in calls[0]


def test_development_compile_passes_and_submission_fixture_fails() -> None:
    with tempfile.TemporaryDirectory(prefix="aria-thesis-release-") as directory:
        output = Path(directory)
        command = [
            "typst",
            "compile",
            "--root",
            "docs",
            str(ROOT / "docs/typst/thesis/tests/release-development.typ"),
            str(output / "development.pdf"),
        ]
        development = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        assert development.returncode == 0, development.stderr
        smoke = ROOT / "docs/typst/thesis/tests/report_data_smoke.typ"
        fixture = subprocess.run(
            [
                "typst",
                "compile",
                "--root",
                "docs",
                "--input",
                "aria-thesis-mode=submission",
                "--input",
                "aria-thesis-data=/typst/thesis/data/report-bundle-fixture.json",
                "--input",
                "aria-thesis-evidence-status=confirmatory",
                "--input",
                "aria-code-ref=" + "a" * 40,
                str(smoke),
                str(output / "fixture.pdf"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert fixture.returncode != 0


def test_typst_rejects_nonhex_code_ref() -> None:
    result = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            "docs",
            "--input",
            "aria-thesis-mode=submission",
            "--input",
            "aria-thesis-data=/typst/thesis/data/report-bundle-fixture.json",
            "--input",
            "aria-thesis-evidence-status=confirmatory",
            "--input",
            "aria-code-ref=" + "z" * 40,
            "docs/typst/thesis/tests/report_data_smoke.typ",
            "/tmp/aria-thesis-invalid-code-ref.pdf",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_typst_rejects_evidence_fixture_notice_and_report_ref_mismatch(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (ROOT / "docs/typst/thesis/data/report-bundle-fixture.json").read_text(
            encoding="utf-8"
        )
    )
    payload["bundle_role"] = "evidence"
    payload["source_revision"] = "a" * 40
    for table in payload["tables"].values():
        if "rows" in table:
            for row in table["rows"]:
                if "status" in row:
                    row["status"] = "confirmatory"
                if "source_revision" in row:
                    row["source_revision"] = "a" * 40
    smoke = ROOT / "docs/typst/thesis/tests/report_data_smoke.typ"
    data_dir = ROOT / "docs/typst/thesis/data"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", dir=data_dir, delete=False, encoding="utf-8"
    ) as handle:
        report = Path(handle.name)
        json.dump(payload, handle)
    try:
        virtual_report = RELEASE.typst_report_path(ROOT, report)
        fixture_notice = subprocess.run(
            [
                "typst",
                "compile",
                "--root",
                "docs",
                "--input",
                "aria-thesis-mode=submission",
                "--input",
                f"aria-thesis-data={virtual_report}",
                "--input",
                "aria-thesis-evidence-status=confirmatory",
                "--input",
                "aria-code-ref=" + "a" * 40,
                str(smoke),
                str(tmp_path / "notice.pdf"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert fixture_notice.returncode != 0
        assert "fixture_notice" in fixture_notice.stderr
        payload.pop("fixture_notice")
        report.write_text(json.dumps(payload), encoding="utf-8")
        mismatch = subprocess.run(
            [
                "typst",
                "compile",
                "--root",
                "docs",
                "--input",
                "aria-thesis-mode=submission",
                "--input",
                f"aria-thesis-data={virtual_report}",
                "--input",
                "aria-thesis-evidence-status=confirmatory",
                "--input",
                "aria-code-ref=" + "b" * 40,
                str(smoke),
                str(tmp_path / "mismatch.pdf"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert mismatch.returncode != 0
        assert "source_revision" in mismatch.stderr
    finally:
        report.unlink(missing_ok=True)


def test_typst_report_path_rejects_host_absolute_path_and_maps_docs_path(
    tmp_path: Path,
) -> None:
    report = tmp_path / "docs/typst/thesis/data/report.json"
    report.parent.mkdir(parents=True)
    report.write_text("{}", encoding="utf-8")
    assert (
        RELEASE.typst_report_path(tmp_path, report) == "/typst/thesis/data/report.json"
    )
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="under <root>/docs"):
        RELEASE.typst_report_path(tmp_path, tmp_path / "outside/report.json")


@pytest.mark.parametrize(
    ("field", "mutation"),
    [
        ("source_date_or_version", lambda row: row.pop("source_date_or_version")),
        ("source_date_or_version", lambda row: row.update(source_date_or_version="")),
        ("date_checked", lambda row: row.pop("date_checked")),
        ("date_checked", lambda row: row.update(date_checked="")),
        ("responsible_owner", lambda row: row.pop("responsible_owner")),
        ("responsible_owner", lambda row: row.update(responsible_owner="")),
        ("proof_kind", lambda row: row.pop("proof_kind")),
        ("proof_kind", lambda row: row.update(proof_kind="")),
        ("required_state", lambda row: row.pop("required_state")),
        ("required_state", lambda row: row.update(required_state="")),
        ("current_state", lambda row: row.pop("current_state")),
        ("current_state", lambda row: row.update(current_state="")),
        ("blocker_rationale", lambda row: row.pop("blocker_rationale")),
        ("blocker_rationale", lambda row: row.update(blocker_rationale="")),
    ],
)
def test_release_requirement_fields_reject_blank_or_missing(
    field: str, mutation
) -> None:
    data = copy.deepcopy(RELEASE.load_release_requirements())
    mutation(data["requirements"][0])
    with pytest.raises(RELEASE.ReleaseRequirementsError, match=field):
        RELEASE.validate_release_requirements(data)


def test_release_requirement_rejects_malformed_url() -> None:
    data = copy.deepcopy(RELEASE.load_release_requirements())
    data["requirements"][0]["source_urls"] = ["not-a-url"]
    with pytest.raises(RELEASE.ReleaseRequirementsError, match="HTTP source_urls"):
        RELEASE.validate_release_requirements(data)
