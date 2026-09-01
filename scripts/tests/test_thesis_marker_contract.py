"""Verify the development/submission Typst marker contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = ROOT / "docs" / "typst" / "thesis" / "tests"


def _compile(
    fixture: str,
    output_dir: Path,
    *,
    mode: str | None = None,
    expect_success: bool,
) -> None:
    command = [
        os.environ.get("TYPST", "typst"),
        "compile",
        "--root",
        "docs",
    ]
    if mode is not None:
        command.extend(["--input", f"aria-thesis-mode={mode}"])
    command.extend(
        [
            str(TEST_ROOT / f"{fixture}.typ"),
            str(output_dir / f"{fixture}.pdf"),
        ]
    )
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    succeeded = result.returncode == 0
    if succeeded != expect_success:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        expectation = "pass" if expect_success else "fail"
        raise AssertionError(
            f"{fixture} expected to {expectation}, got {result.returncode}:\n{output}"
        )


def _query_metadata(
    fixture: str,
    selector: str,
    *,
    mode: str | None = None,
) -> list[str]:
    command = [os.environ.get("TYPST", "typst"), "query", "--root", "docs"]
    if mode is not None:
        command.extend(["--input", f"aria-thesis-mode={mode}"])
    command.extend([str(TEST_ROOT / f"{fixture}.typ"), selector, "--field", "value"])
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise AssertionError(f"metadata query failed for {fixture}:\n{output}")
    values = json.loads(result.stdout)
    return values if isinstance(values, list) else [values]


def _pdf_text(path: Path) -> str:
    result = subprocess.run(
        [os.environ.get("PDFTOTEXT", "pdftotext"), str(path), "-"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        raise AssertionError(f"PDF text extraction failed for {path.name}:\n{output}")
    return " ".join(result.stdout.split())


def main() -> None:
    positive = (("marker-development", None), ("marker-submission", "submission"))
    invalid = (
        "promotion-invalid-empty-target",
        "promotion-invalid-empty",
        "promotion-invalid-empty-gate",
        "promotion-invalid-empty-disposition",
        "promotion-invalid-empty-summary",
        "promotion-invalid-unknown",
        "promotion-invalid-missing",
        "scientific-core-todo-invalid-priority",
        "scientific-core-todo-invalid-domain",
        "scientific-core-todo-invalid-readiness",
        "scientific-core-todo-invalid-blocker",
    )
    with tempfile.TemporaryDirectory(prefix="aria-nbv-thesis-markers-") as temp:
        output_dir = Path(temp)
        for fixture, mode in positive:
            _compile(fixture, output_dir, mode=mode, expect_success=True)
        for fixture in invalid:
            _compile(fixture, output_dir, expect_success=False)
        _compile(
            "todo-marker-submission",
            output_dir,
            mode="submission",
            expect_success=False,
        )
        _compile(
            "status-marker-submission",
            output_dir,
            mode="submission",
            expect_success=False,
        )
        _compile(
            "scientific-core-todo-development",
            output_dir,
            expect_success=True,
        )
        _compile(
            "scientific-core-todo-submission",
            output_dir,
            mode="submission",
            expect_success=False,
        )
        _compile("declaration", output_dir, expect_success=True)
        declaration_text = _pdf_text(output_dir / "declaration.pdf")
        for clause in (
            "selbstständig verfasst",
            "noch nicht anderweitig für Prüfungszwecke vorgelegt",
            "keine anderen als die angegebenen Quellen oder Hilfsmittel benutzt",
            "wörtliche oder sinngemäße Zitate als solche gekennzeichnet",
        ):
            assert clause in declaration_text, clause
        assert _query_metadata("marker-development", "<marker-development>") == [
            "development-present"
        ]
        scientific_todos = _query_metadata(
            "scientific-core-todo-development", "<scientific-core-todo>"
        )
        assert scientific_todos == [
            {
                "domain": "architecture",
                "priority": "C1",
                "readiness": "blocked",
                "claim": "[exact horizon-two recovery]",
                "gate": "[frozen actor-visible corpus]",
                "source": "[method-alternatives.typ]",
                "blocked_by": "[data admission]",
            }
        ]
        for disposition in ("candidate", "blocked", "deferred", "rejected"):
            selector = f"<marker-promotion-{disposition}>"
            assert _query_metadata("marker-development", selector) == [
                f"promotion-{disposition}-present"
            ]
        assert (
            _query_metadata(
                "marker-submission", "<marker-development>", mode="submission"
            )
            == []
        )
        assert _query_metadata(
            "marker-submission", "<marker-submission>", mode="submission"
        ) == ["submission-present"]
        for disposition in ("candidate", "blocked", "deferred", "rejected"):
            assert (
                _query_metadata(
                    "marker-submission",
                    f"<marker-promotion-{disposition}>",
                    mode="submission",
                )
                == []
            )
        assert (
            _query_metadata(
                "marker-submission", "<marker-promotion-invalid>", mode="submission"
            )
            == []
        )
    print("thesis marker contract passed")


if __name__ == "__main__":
    main()
