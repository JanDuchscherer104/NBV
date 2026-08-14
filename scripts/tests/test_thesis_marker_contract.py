"""Verify the development/submission Typst marker contract."""

from __future__ import annotations

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
    print("thesis marker contract passed")


if __name__ == "__main__":
    main()
