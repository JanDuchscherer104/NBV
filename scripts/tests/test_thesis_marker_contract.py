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
        assert _query_metadata("marker-development", "<marker-development>") == [
            "development-present"
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
        for disposition in ("candidate", "blocked", "deferred", "rejected"):
            assert (
                _query_metadata(
                    "marker-submission",
                    f"<marker-promotion-{disposition}>",
                    mode="submission",
                )
                == []
            )
    print("thesis marker contract passed")


if __name__ == "__main__":
    main()
