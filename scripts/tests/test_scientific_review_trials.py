from __future__ import annotations

import sys
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))

import run_scientific_review_trials as trials  # noqa: E402
import trial_harness as harness  # noqa: E402


def _fixtures() -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
    original = {
        "id": "finding",
        "author_id": "author",
        "task": "Review candidate:\noriginal",
        "candidate": "original",
    }
    corrected = {
        "id": "finding-corrected",
        "author_id": "author",
        "task": "Review candidate:\ncorrected",
        "candidate": "corrected",
    }
    original_rubric = {
        "id": "finding",
        "case_kind": "original",
        "source_id": "finding",
        "expected_category": "confounding",
        "severity_min": "medium",
        "severity_max": "high",
        "wording_variant_of": None,
        "resolution_of": None,
        "related_ids": ["finding-corrected"],
    }
    corrected_rubric = {
        "id": "finding-corrected",
        "case_kind": "corrected",
        "source_id": "finding",
        "expected_category": None,
        "severity_min": None,
        "severity_max": None,
        "wording_variant_of": None,
        "resolution_of": "finding",
        "related_ids": [],
    }
    return (
        {"finding": original, "finding-corrected": corrected},
        {"finding": original_rubric, "finding-corrected": corrected_rubric},
    )


class _EmptyAdapter:
    def load_fixtures(self, fixture_bytes: object) -> object:
        return fixture_bytes

    def select_cases(
        self, fixtures: object, *, selected_ids: tuple[str, ...], all_cases: bool
    ) -> tuple[harness.TrialCase, ...]:
        return ()


def test_explicit_zero_match_selection_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(harness, "run_git", lambda *args, **kwargs: "commit")
    spec = harness.SuiteSpec(
        tested_ref="HEAD",
        rubric_ref="HEAD",
        identity=harness.SuiteIdentity("test", "dirty", "test-"),
        fixture_paths=(),
        output_root=tmp_path,
        trial_schema=tmp_path / "trial.json",
        verifier_schema=tmp_path / "verifier.json",
        selected_ids=("does-not-exist",),
    )

    with pytest.raises(ValueError, match="resolved to zero trial cases"):
        harness.run_suite(spec, _EmptyAdapter())


def test_repository_scientific_review_fixtures_load() -> None:
    prompts = trials.load_prompts()
    rubric = trials.load_rubric()

    assert set(prompts) == set(rubric) == set(trials.DEFAULT_TRIAL_IDS)


def test_corrected_only_selection_closes_over_repository_original() -> None:
    _, rubric = _fixtures()
    assert trials._initial_selection(("finding-corrected",), rubric) == ("finding",)


def test_corrected_selection_requires_original_source_evidence() -> None:
    prompts, rubric = _fixtures()
    adapter = trials.ScientificReviewAdapter()
    with pytest.raises(ValueError, match="resolution metadata is malformed"):
        adapter.select_cases(
            (prompts, rubric), selected_ids=("finding-corrected",), all_cases=False
        )


def test_corrected_selection_succeeds_with_persisted_original_report() -> None:
    prompts, rubric = _fixtures()
    original_hash = "a" * 64
    original = prompts["finding"]["candidate"]
    link = trials.resolution_link(
        original_trial_id="finding",
        candidate_hash=trials.candidate_sha256(original),
        report_hash=original_hash,
        category="confounding",
    )
    adapter = trials.ScientificReviewAdapter(
        {"finding-corrected": link}, {"finding": original_hash}
    )

    cases = adapter.select_cases(
        (prompts, rubric), selected_ids=("finding-corrected",), all_cases=False
    )

    assert [case.trial_id for case in cases] == ["finding-corrected"]
    assert cases[0].adapter_metadata == {"resolution": link}


def test_scientific_review_cli_list_only_is_executable() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "scaffold" / "run_scientific_review_trials.py"),
            "--list",
            "--id",
            "seminar-uncontrolled-ablation-corrected",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "seminar-uncontrolled-ablation-corrected"
