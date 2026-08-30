"""Compile the positive and negative Typst report-data contract fixtures."""

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
    expect_success: bool,
    expected_error: str | None = None,
) -> None:
    result = subprocess.run(
        [
            os.environ.get("TYPST", "typst"),
            "compile",
            "--root",
            "docs",
            str(TEST_ROOT / f"{fixture}.typ"),
            str(output_dir / f"{fixture}.pdf"),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    succeeded = result.returncode == 0
    if succeeded != expect_success:
        output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        expectation = "pass" if expect_success else "fail"
        raise AssertionError(
            f"{fixture} expected to {expectation}, got {result.returncode}:\n{output}"
        )
    if expected_error is not None and expected_error not in result.stderr:
        raise AssertionError(
            f"{fixture} did not fail through the expected lookup contract:\n{result.stderr}"
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aria-nbv-report-data-") as temp:
        output_dir = Path(temp)
        _compile("report_data_smoke", output_dir, expect_success=True)
        _compile("evidence_gate_state", output_dir, expect_success=True)
        _compile("learning_gate_evidence_contract", output_dir, expect_success=True)
        _compile("recovery_evidence_contract", output_dir, expect_success=True)
        expected_lookup_error = (
            "expected one thesis report fact for store and key: store-a / metric"
        )
        _compile(
            "report_store_fact_duplicate",
            output_dir,
            expect_success=False,
            expected_error=expected_lookup_error,
        )
        _compile(
            "report_store_fact_missing",
            output_dir,
            expect_success=False,
            expected_error=expected_lookup_error,
        )
    print("Typst report data contract passed")


if __name__ == "__main__":
    main()
