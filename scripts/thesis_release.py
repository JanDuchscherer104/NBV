"""Fail-closed audit and submission gates for the G006 thesis release."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "docs/typst/thesis/release-requirements.toml"
LOCK_RELATIVE_PATH = Path("docs/typst/thesis/toolchain-lock.json")
LOCK_PLACEHOLDER = "PENDING_GENERATED_AFTER_IMPLEMENTATION_COMMIT"
COMMIT_OID = re.compile(r"^[0-9a-f]{40}$")
CONFIRMATORY_BLOCKER = (
    "no validated population-level rollout bundle with paired endpoint"
)
REQUIREMENT_IDS = {
    "hm.independent-work",
    "hm.citations",
    "hm.submission",
    "hm.gwp-documentation",
    "hm.ai-disclosure",
    "ml.claim-scope",
    "ml.reproducibility",
    "ml.uncertainty",
    "ml.compute",
}
CLASSIFICATIONS = {"binding_hm", "institutional_guidance", "nonbinding_ml_overlay"}
PROOF_KINDS = {"deterministic", "manual"}


class ReleaseRequirementsError(ValueError):
    """Raised when release inputs would permit an unsafe submission."""


def load_release_requirements(path: Path = LEDGER_PATH) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _string(record: dict[str, Any], key: str, context: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ReleaseRequirementsError(f"{context} requires non-empty {key}")
    return value


def _git_revision(root: Path) -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseRequirementsError("unable to resolve a real HEAD commit") from exc
    if not COMMIT_OID.fullmatch(revision):
        raise ReleaseRequirementsError(
            "HEAD is not an exact lower-hex 40-character commit"
        )
    return revision


def _require_real_commit(root: Path, revision: object) -> str:
    if not isinstance(revision, str) or not COMMIT_OID.fullmatch(revision):
        raise ReleaseRequirementsError(
            "toolchain lock source_revision must be lower-hex 40-character commit"
        )
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReleaseRequirementsError(
            "toolchain lock source_revision is not a real git commit"
        ) from exc
    return revision


def _validate_lock_schema(root: Path, payload: object, *, final: bool = True) -> None:
    try:
        schema = json.loads(
            (
                root / "scripts/scaffold/schemas/thesis-toolchain-lock.schema.json"
            ).read_text(encoding="utf-8")
        )
        spec = importlib.util.spec_from_file_location(
            "thesis_toolchain_lock", root / "scripts/thesis_toolchain_lock.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError("unable to load thesis_toolchain_lock")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not final:
            schema["properties"]["toolchain"]["required"].remove("pdf_comparator")
        module._schema_validate(payload, schema)
    except (
        ImportError,
        OSError,
        json.JSONDecodeError,
        AttributeError,
        RuntimeError,
    ) as exc:
        raise ReleaseRequirementsError(
            "toolchain lock does not satisfy its full schema"
        ) from exc


def _validate_ledger(
    data: dict[str, Any],
    root: Path,
    *,
    final: bool = False,
    lock_root: Path | None = None,
) -> dict[str, Any] | None:
    if data.get("schema_version") != "aria-nbv-thesis-release-requirements-v1":
        raise ReleaseRequirementsError("unsupported release requirements schema")
    checked_date = data.get("date_checked")
    if not isinstance(checked_date, str):
        raise ReleaseRequirementsError(
            "release ledger date_checked must be an ISO date"
        )
    try:
        date.fromisoformat(checked_date)
    except ValueError as exc:
        raise ReleaseRequirementsError(
            "release ledger date_checked must be an ISO date"
        ) from exc
    requirements = data.get("requirements")
    if (
        not isinstance(requirements, list)
        or {r.get("id") for r in requirements if isinstance(r, dict)} != REQUIREMENT_IDS
        or len(requirements) != len(REQUIREMENT_IDS)
    ):
        raise ReleaseRequirementsError(
            "release requirement IDs are missing, duplicated, or unexpected"
        )
    for row in requirements:
        if not isinstance(row, dict):
            raise ReleaseRequirementsError("each release requirement must be a table")
        context = f"requirement {row.get('id', '<missing>')}"
        for field in (
            "id",
            "source_date_or_version",
            "responsible_owner",
            "required_state",
            "current_state",
            "blocker_rationale",
        ):
            _string(row, field, context)
        urls = row.get("source_urls")
        if (
            not isinstance(urls, list)
            or not urls
            or not all(
                isinstance(url, str) and url.startswith(("http://", "https://"))
                for url in urls
            )
        ):
            raise ReleaseRequirementsError(f"{context} requires HTTP source_urls")
        if (
            row.get("classification") not in CLASSIFICATIONS
            or row.get("proof_kind") not in PROOF_KINDS
        ):
            raise ReleaseRequirementsError(
                f"{context} has invalid classification or proof_kind"
            )
        if row.get("date_checked") != checked_date:
            raise ReleaseRequirementsError(f"{context} has stale date_checked")
        if row["id"].startswith("ml.") and row["classification"] == "binding_hm":
            raise ReleaseRequirementsError(
                "ML venue guidance cannot be represented as binding HM"
            )
        if row["id"] == "hm.submission":
            required = (
                "https://cs.hm.edu/studierende/abschlussarbeiten.de.html",
                "Anleitung_Anmeldung_Abschlussarbeit_Stand_29.09.2025.pdf",
                "Anleitung_Abgabe_Abschlussarbeit_Stand_29.09.2025.pdf",
            )
            if not all(any(token in url for url in urls) for token in required):
                raise ReleaseRequirementsError(
                    "hm.submission must cite the public FK07 and PRIMUSS guides"
                )
        if "acm.org" in " ".join(urls):
            raise ReleaseRequirementsError(
                "ACM policy requires a separate unverified revalidation record"
            )

    submission = data.get("submission")
    if (
        not isinstance(submission, dict)
        or submission.get("local_submission_claim") is not False
    ):
        raise ReleaseRequirementsError(
            "local release state must never claim submission"
        )
    for key in (
        "required_state",
        "current_state",
        "assigned_spo_state",
        "primuss_state",
        "blocker_rationale",
    ):
        _string(submission, key, "submission")
    if (
        submission["assigned_spo_state"] != "manual_pending"
        or submission["primuss_state"] != "manual_pending"
    ):
        raise ReleaseRequirementsError(
            "external submission state must remain human-pending"
        )
    if CONFIRMATORY_BLOCKER not in submission["blocker_rationale"].lower():
        raise ReleaseRequirementsError(
            "submission must record the precise missing confirmatory-evidence blocker"
        )
    for section_name, expected in (
        ("declaration", "docs/typst/thesis/template/layout/disclaimer.typ"),
        ("ai_disclosure", "docs/typst/thesis/main.typ"),
    ):
        section = data.get(section_name)
        if not isinstance(section, dict):
            raise ReleaseRequirementsError(f"{section_name} state is missing")
        for key in (
            "source_path",
            "presence",
            "required_state",
            "current_state",
            "responsible_owner",
            "proof_kind",
            "blocker_rationale",
        ):
            _string(section, key, section_name)
        if (
            section["source_path"] != expected
            or section["presence"] not in {"present", "not_applicable"}
            or section["proof_kind"] not in PROOF_KINDS
        ):
            raise ReleaseRequirementsError(f"{section_name} has invalid owner or state")
        if (
            section_name == "declaration"
            and section.get("wording_approval") != "manual_pending"
        ):
            raise ReleaseRequirementsError(
                "declaration wording_approval must remain manual_pending"
            )
    if (
        "Ich versichere, dass ich diese #thesisKindGerman selbststaendig verfasst"
        not in (root / "docs/typst/thesis/template/layout/disclaimer.typ").read_text(
            encoding="utf-8"
        )
    ):
        raise ReleaseRequirementsError(
            "declaration wording is missing from disclaimer.typ"
        )
    if "Generative-AI tools" not in (root / "docs/typst/thesis/main.typ").read_text(
        encoding="utf-8"
    ):
        raise ReleaseRequirementsError("AI-use disclosure is missing from main.typ")
    if (
        'style: "/ieee.csl"'
        not in (
            root / "docs/typst/thesis/template/layout/thesis_template.typ"
        ).read_text(encoding="utf-8")
        or not (root / "docs/ieee.csl").is_file()
    ):
        raise ReleaseRequirementsError("tracked IEEE bibliography path is missing")

    lock = data.get("toolchain_lock")
    if not isinstance(lock, dict) or lock.get("path") != LOCK_RELATIVE_PATH.as_posix():
        raise ReleaseRequirementsError(
            "toolchain lock path is not the generated lock owner"
        )
    lock_path = (lock_root or root) / LOCK_RELATIVE_PATH
    lock_sha = lock.get("sha256")
    if not isinstance(lock_sha, str) or not lock_sha:
        raise ReleaseRequirementsError("toolchain lock sha256 is missing")
    if lock_path.is_file():
        actual_sha = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if lock_sha != actual_sha or lock.get("sha256_state") != "verified":
            raise ReleaseRequirementsError(
                "toolchain lock SHA-256 or verification state does not match"
            )
        try:
            raw_payload = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReleaseRequirementsError("toolchain lock is not valid JSON") from exc
        if not isinstance(raw_payload, dict):
            raise ReleaseRequirementsError("toolchain lock must be a JSON object")
        payload: dict[str, Any] = raw_payload
        _validate_lock_schema(root, payload, final=final)
        _require_real_commit(root, payload.get("source_revision"))
        return payload
    if lock_sha != LOCK_PLACEHOLDER or lock.get("sha256_state") != "pending":
        raise ReleaseRequirementsError(
            "missing generated lock requires the explicit pending placeholder"
        )
    if final:
        raise ReleaseRequirementsError(
            "final release verification requires the generated toolchain lock"
        )
    return None


def validate_release_requirements(
    data: dict[str, Any],
    root: Path = ROOT,
    *,
    final: bool = False,
    lock_root: Path | None = None,
) -> dict[str, Any] | None:
    """Validate the release ledger and return the verified lock when present."""
    return _validate_ledger(data, root, final=final, lock_root=lock_root)


def _claims_model(root: Path) -> Any:
    sys.path.insert(0, str(root / "scripts"))
    import check_thesis_claims

    return check_thesis_claims.read_principal_claims(
        root / "docs/typst/thesis/data/principal-claims.toml", root
    )


def validate_confirmatory_claims(model: Any) -> None:
    bad = [
        claim.id
        for claim in model.claims
        if (claim.maturity, claim.review_state, claim.release_state)
        != ("confirmatory", "approved", "admissible")
    ]
    if bad:
        raise ReleaseRequirementsError(
            "real claims/evidence are withheld: " + ", ".join(bad)
        )


def load_report(
    path: Path, source_revision: str, *, root: Path | None = None
) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseRequirementsError(
            f"unable to read explicit report: {path}"
        ) from exc
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != "aria-nbv-thesis-report-v2"
    ):
        raise ReleaseRequirementsError("report must use aria-nbv-thesis-report-v2")
    if report.get("bundle_role") != "evidence" or "fixture_notice" in report:
        raise ReleaseRequirementsError(
            "submission report must be a real evidence bundle without fixture_notice"
        )
    report_revision = report.get("source_revision")
    if (
        not isinstance(report_revision, str)
        or not COMMIT_OID.fullmatch(report_revision)
        or report_revision != source_revision
    ):
        raise ReleaseRequirementsError(
            "report source_revision must equal the final lock source_revision"
        )
    tables = report.get("tables")
    empirical = tables.get("empirical_results") if isinstance(tables, dict) else None
    rows = empirical.get("rows") if isinstance(empirical, dict) else None
    if (
        not isinstance(rows, list)
        or not rows
        or any(
            not isinstance(row, dict)
            or row.get("status") != "confirmatory"
            or row.get("source_revision") != report_revision
            for row in rows
        )
    ):
        raise ReleaseRequirementsError(
            "report must contain confirmatory empirical results with matching provenance"
        )
    if root is not None:
        _validate_report_provenance_exact_root(
            root=root, report=path, source_revision=source_revision
        )
    return report


def _validate_report_provenance_exact_root(
    *, root: Path, report: Path, source_revision: str
) -> None:
    """Run the canonical report validator from the supplied checkout."""

    bridge = (
        "import json, sys; "
        "from pathlib import Path; "
        "from aria_nbv.rollouts.reporting import validate_thesis_report_provenance; "
        "payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')); "
        "validate_thesis_report_provenance(payload, "
        "evidence_root=Path(sys.argv[1]).parent, expected_source_revision=sys.argv[2])"
    )
    environment = os.environ.copy()
    package_root = str((root / "aria_nbv").resolve())
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        package_root
        if not existing_pythonpath
        else os.pathsep.join((package_root, existing_pythonpath))
    )
    try:
        subprocess.run(
            [sys.executable, "-c", bridge, str(report), source_revision],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ReleaseRequirementsError(
            f"serialized evidence bundle provenance validation failed: {detail.strip()}"
        ) from exc


def _check_toolchain_lock(
    *, root: Path, typst_bin: str, pdftoppm_bin: str = "pdftoppm"
) -> None:
    lock_path = root / LOCK_RELATIVE_PATH
    try:
        subprocess.run(
            [
                sys.executable,
                str(root / "scripts/thesis_toolchain_lock.py"),
                "check",
                "--root",
                str(root),
                "--output",
                str(lock_path),
                "--typst-bin",
                typst_bin,
                "--pdftoppm-bin",
                pdftoppm_bin,
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ReleaseRequirementsError(
            "toolchain lock check failed; Typst submission compile was not started: "
            + detail.strip()
        ) from exc


def _rasterized_pages(
    *, pdf: Path, output_dir: Path, pdftoppm_bin: str, ppi: int
) -> list[Path]:
    prefix = output_dir / "page"
    try:
        subprocess.run(
            [pdftoppm_bin, "-r", str(ppi), "-png", str(pdf), str(prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise ReleaseRequirementsError(
            f"PDF rasterization failed: {detail.strip()}"
        ) from exc
    pages = list(output_dir.glob("page-*.png"))
    pages.sort(key=lambda path: int(path.stem.rsplit("-", 1)[1]))
    return pages


def _compare_rasterized_pages(
    fresh_pages: list[Path], tracked_pages: list[Path]
) -> None:
    if len(fresh_pages) != len(tracked_pages):
        raise ReleaseRequirementsError(
            "tracked final PDF differs from a fresh compile: page count mismatch"
        )
    for index, (fresh_page, tracked_page) in enumerate(
        zip(fresh_pages, tracked_pages, strict=True), start=1
    ):
        if (
            hashlib.sha256(fresh_page.read_bytes()).digest()
            != hashlib.sha256(tracked_page.read_bytes()).digest()
        ):
            raise ReleaseRequirementsError(
                "tracked final PDF differs from a fresh compile: "
                f"page {index} raster hash mismatch"
            )


def _final_pdf_freshness(
    *, root: Path, typst_bin: str, pdftoppm_bin: str, lock: dict[str, Any]
) -> None:
    tracked_pdf = root / "docs/typst/thesis/main.pdf"
    if not tracked_pdf.is_file():
        raise ReleaseRequirementsError("tracked final PDF is missing")
    comparator = lock.get("toolchain", {}).get("pdf_comparator", {})
    if comparator.get("command") != Path(pdftoppm_bin).name:
        raise ReleaseRequirementsError("PDF comparator identity drift detected")
    actual_comparator = shutil.which(pdftoppm_bin) or pdftoppm_bin
    if Path(actual_comparator).name != comparator.get("command"):
        raise ReleaseRequirementsError("PDF comparator identity drift detected")
    ppi = comparator.get("ppi")
    if ppi != 72:
        raise ReleaseRequirementsError("PDF comparator PPI is not fixed at 72")

    with tempfile.TemporaryDirectory(prefix="aria-thesis-final-") as directory:
        temporary = Path(directory)
        fresh_pdf = temporary / "fresh.pdf"
        try:
            subprocess.run(
                [
                    typst_bin,
                    "compile",
                    "--root",
                    "docs",
                    str(root / "docs/typst/thesis/main.typ"),
                    str(fresh_pdf),
                ],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            detail = getattr(exc, "stderr", "") or str(exc)
            raise ReleaseRequirementsError(
                f"fresh final PDF compile failed: {detail.strip()}"
            ) from exc
        fresh_pages_dir = temporary / "fresh-pages"
        fresh_pages_dir.mkdir()
        fresh_pages = _rasterized_pages(
            pdf=fresh_pdf,
            output_dir=fresh_pages_dir,
            pdftoppm_bin=actual_comparator,
            ppi=ppi,
        )
        tracked_pages_dir = temporary / "tracked-pages"
        tracked_pages_dir.mkdir()
        tracked_pages = _rasterized_pages(
            pdf=tracked_pdf,
            output_dir=tracked_pages_dir,
            pdftoppm_bin=actual_comparator,
            ppi=ppi,
        )
        _compare_rasterized_pages(fresh_pages, tracked_pages)


def typst_report_path(root: Path, report: Path) -> str:
    """Map a repository docs report to Typst's virtual /typst namespace."""
    root = root.resolve()
    report = report.resolve()
    docs = (root / "docs").resolve()
    try:
        relative = report.relative_to(docs / "typst")
    except ValueError as exc:
        raise ReleaseRequirementsError(
            "submission report must be under <root>/docs"
        ) from exc
    return "/typst/" + relative.as_posix()


def build_submission(
    *, root: Path = ROOT, report: Path, output: Path, typst_bin: str = "typst"
) -> None:
    ledger = load_release_requirements(root / LEDGER_PATH.relative_to(ROOT))
    # Report the scientific blocker before the not-yet-generated release lock;
    # this keeps the current strict failure about withheld real evidence.
    validate_release_requirements(ledger, root)
    validate_confirmatory_claims(_claims_model(root))
    lock = validate_release_requirements(ledger, root, final=True)
    assert lock is not None
    virtual_report = typst_report_path(root, report)
    load_report(report, lock["source_revision"], root=root)
    _check_toolchain_lock(root=root, typst_bin=typst_bin)
    command = [
        typst_bin,
        "compile",
        "--root",
        "docs",
        str(root / "docs/typst/thesis/main.typ"),
        str(output),
        "--input",
        "aria-thesis-mode=submission",
        "--input",
        f"aria-thesis-data={virtual_report}",
        "--input",
        "aria-thesis-evidence-status=confirmatory",
        "--input",
        f"aria-code-ref={lock['source_revision']}",
    ]
    subprocess.run(command, cwd=root, check=True)


def _resolve_cli_path(root: Path, path: Path) -> Path:
    """Resolve relative CLI paths within the selected checkout."""
    return (path if path.is_absolute() else root / path).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--root", type=Path, default=ROOT)
    audit.add_argument(
        "--final",
        action="store_true",
        help="require and verify the generated final lock",
    )
    audit.add_argument("--typst-bin", default=os.environ.get("TYPST", "typst"))
    audit.add_argument("--pdftoppm-bin", default=os.environ.get("PDFTOPPM", "pdftoppm"))
    build = sub.add_parser("submission-build")
    build.add_argument("--root", type=Path, default=ROOT)
    build.add_argument("--report", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--typst-bin", default=os.environ.get("TYPST", "typst"))
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "audit":
            _check_toolchain_lock(
                root=root, typst_bin=args.typst_bin, pdftoppm_bin=args.pdftoppm_bin
            )
            lock = validate_release_requirements(
                load_release_requirements(root / LEDGER_PATH.relative_to(ROOT)),
                root,
                final=args.final,
            )
            if args.final:
                assert lock is not None
                _final_pdf_freshness(
                    root=root,
                    typst_bin=args.typst_bin,
                    pdftoppm_bin=args.pdftoppm_bin,
                    lock=lock,
                )
            print("thesis release audit passed; submission remains externally blocked")
        else:
            build_submission(
                root=root,
                report=_resolve_cli_path(root, args.report),
                output=_resolve_cli_path(root, args.output),
                typst_bin=args.typst_bin,
            )
            print(f"submission build: {args.output}")
    except (OSError, ReleaseRequirementsError, subprocess.CalledProcessError) as exc:
        print(f"thesis release: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
