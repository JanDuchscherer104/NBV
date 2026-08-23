from __future__ import annotations

import hashlib
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "scaffold"))

import run_scientific_review_trials as trials  # noqa: E402
import trial_harness as harness  # noqa: E402
from trial_harness import (  # noqa: E402
    PrincipalIdentity,
    ReviewerProvenance,
    TrialCase,
    _candidate_report,
)


def _case(trial_id: str) -> TrialCase:
    prompt = trials.load_prompts()[trial_id]
    rubric = trials.load_rubric()[trial_id]
    case = TrialCase(
        trial_id,
        (prompt, rubric),
        trials._candidate_provenance(
            candidate=prompt["candidate"],
            author_id=prompt["author_id"],
            trial_id=trial_id,
        ),
    )
    return case


def _report(
    case: TrialCase,
    *,
    reviewer_id: str = "host-user:reviewer@host",
) -> dict[str, Any]:
    assert case.candidate is not None
    return {
        "candidate": {
            "candidate_sha256": trials.candidate_sha256(
                cast(tuple[dict[str, str], dict[str, Any]], case.context)[0][
                    "candidate"
                ]
            ),
            "author": case.candidate.author.as_report(),
        },
        "reviewer": {
            "canonical": reviewer_id,
            "namespace": reviewer_id.split(":", 1)[0],
            "subject": reviewer_id.split(":", 1)[1],
        },
    }


def _adjudication_report(case: TrialCase, primary: object) -> dict[str, Any]:
    return {
        **_report(case),
        "tested_commit": "tested-commit",
        "trial_response": harness.bound_trial_response(primary),
    }


def _hidden_pass(case: TrialCase) -> dict[str, str]:
    prompt, _ = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    return {
        "trial_id": case.trial_id,
        "candidate_sha256": trials.candidate_sha256(prompt["candidate"]),
        "tested_commit": "tested-commit",
        "rubric_commit": "rubric-commit",
        "verdict": "pass",
        "reason": "The primary response matches the hidden rubric.",
    }


def _finding(case: TrialCase) -> dict[str, Any]:
    prompt, rubric = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    candidate = prompt["candidate"]
    return {
        "category": rubric["expected_category"],
        "severity": rubric["severity_min"],
        "evidence": {"line_start": 1, "line_end": 1, "text": candidate},
        "reason": "The candidate crosses the stated evidence boundary.",
        "impact": "The conclusion is not supported by the described design.",
        "action": "Bound the claim and report the missing design evidence.",
    }


def _verdict(
    case: TrialCase, *, findings: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    prompt, _ = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    findings = findings or []
    return {
        "trial_id": case.trial_id,
        "candidate_sha256": trials.candidate_sha256(prompt["candidate"]),
        "outcome": {"clear": not findings, "findings": findings},
    }


def test_fixture_sets_cover_controls_and_corrections() -> None:
    prompts = trials.load_prompts()
    rubric = trials.load_rubric()
    assert set(prompts) == set(rubric) == set(trials.DEFAULT_TRIAL_IDS)
    assert {item["expected_category"] for item in rubric.values()} == {
        "confounding",
        "actor_oracle_leakage",
        "invalidity_utility",
        "claim_escalation",
        "experimental_units",
        "uncertainty",
        "implementation_status",
        None,
    }
    assert {
        trial_id: (rubric[trial_id]["severity_min"], rubric[trial_id]["severity_max"])
        for trial_id in trials.DEFAULT_TRIAL_IDS[:7]
    } == {
        "seminar-uncontrolled-ablation": ("high", "critical"),
        "actor-oracle-leakage": ("critical", "critical"),
        "invalidity-as-utility": ("high", "critical"),
        "pilot-escalation": ("high", "critical"),
        "pseudoreplication": ("high", "critical"),
        "missing-uncertainty": ("medium", "high"),
        "planned-tense-drift": ("medium", "high"),
    }
    for trial_id, fixture in rubric.items():
        assert fixture["source_id"] in prompts
        if fixture["case_kind"] == "variant":
            assert fixture["wording_variant_of"] == fixture["source_id"]
            source = rubric[fixture["source_id"]]
            assert (fixture["severity_min"], fixture["severity_max"]) == (
                source["severity_min"],
                source["severity_max"],
            )
        if fixture["case_kind"] == "corrected":
            assert fixture["resolution_of"] == fixture["source_id"]
            assert (
                prompts[trial_id]["candidate"]
                != prompts[fixture["source_id"]]["candidate"]
            )


def test_live_negative_candidates_isolate_requested_semantics() -> None:
    prompts = trials.load_prompts()
    seminar = prompts["seminar-uncontrolled-ablation"]
    assert "confounding" in seminar["task"]
    assert "superiority" not in seminar["candidate"]
    uncertainty = prompts["missing-uncertainty"]
    assert "only for missing uncertainty" in uncertainty["task"]
    assert "estimand" not in uncertainty["task"]
    assert all(
        token in uncertainty["candidate"]
        for token in (
            "held-out scenes",
            "mean target reward",
            "normalized reward units",
        )
    )
    assert "decisive" not in uncertainty["candidate"]


def test_trial_prompt_attests_exact_trial_and_candidate_identity() -> None:
    case = _case("missing-uncertainty")
    prompt, _ = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    rendered = trials.build_trial_prompt(case)
    assert f"trial_id must be exactly {case.trial_id!r}" in rendered
    assert (
        f"exact candidate SHA-256 is {trials.candidate_sha256(prompt['candidate'])}"
        in rendered
    )
    assert "candidate-relative 1-based inclusive line span" in rendered
    assert "at most one finding" in rendered
    assert "single most material issue requested by the task" in rendered


def test_prompt_loader_fails_closed_for_malformed_and_duplicate_ids() -> None:
    line = '{"id":"x","author_id":"a","task":"x","candidate":"x"}'
    with pytest.raises(ValueError):
        trials.load_prompts((line + "\n" + line).encode())
    with pytest.raises(ValueError):
        trials.load_prompts(b'{"id":"x","task":"x"}\n')


def test_rubric_loader_fails_closed_for_category_bound_and_shape_errors() -> None:
    base = trials.load_rubric()["restrained-abstract"]
    bad = {"fixtures": [{**base, "expected_category": "novelty"}]}
    with pytest.raises(ValueError):
        trials.load_rubric(json.dumps(bad).encode())
    original = trials.load_rubric()["missing-uncertainty"]
    for malformed in (
        {**original, "severity_min": "high", "severity_max": "medium"},
        {**original, "severity_min": "informational"},
        {**base, "severity_min": "low", "severity_max": "high"},
    ):
        with pytest.raises(ValueError, match="severity"):
            trials.load_rubric(json.dumps({"fixtures": [malformed]}).encode())
    with pytest.raises(ValueError):
        trials.load_rubric(b'{"fixtures":[{"id":"x"}]}')


def test_fixture_links_fail_closed_for_dangling_or_nonreciprocal_records() -> None:
    rubric = trials.load_rubric()
    rubric["seminar-uncontrolled-ablation"]["related_ids"] = ["dangling"]
    with pytest.raises(ValueError, match="dangles|link"):
        trials.ScientificReviewAdapter().load_fixtures(
            {
                trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
                trials.RUBRIC_RELATIVE: json.dumps(
                    {"fixtures": list(rubric.values())}
                ).encode(),
            }
        )


def test_variant_fixture_must_preserve_original_severity_bounds() -> None:
    rubric = trials.load_rubric()
    rubric["missing-uncertainty-variant"]["severity_min"] = "low"
    with pytest.raises(ValueError, match="severity bounds differ"):
        trials.ScientificReviewAdapter().load_fixtures(
            {
                trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
                trials.RUBRIC_RELATIVE: json.dumps(
                    {"fixtures": list(rubric.values())}
                ).encode(),
            }
        )


@pytest.mark.parametrize("trial_id", trials.DEFAULT_TRIAL_IDS[:7])
def test_negative_controls_find_intended_category_with_exact_span(
    trial_id: str,
) -> None:
    case = _case(trial_id)
    valid, reason = trials.validate_verdict(
        _verdict(case, findings=[_finding(case)]), case=case, report=_report(case)
    )
    assert valid, reason


@pytest.mark.parametrize("trial_id", trials.DEFAULT_TRIAL_IDS[7:11])
def test_positive_controls_are_clear(trial_id: str) -> None:
    case = _case(trial_id)
    valid, reason = trials.validate_verdict(
        _verdict(case), case=case, report=_report(case)
    )
    assert valid, reason


@pytest.mark.parametrize("trial_id", trials.DEFAULT_TRIAL_IDS[11:18])
def test_wording_variants_preserve_original_category(trial_id: str) -> None:
    case = _case(trial_id)
    _, variant_rubric = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    finding = _finding(case)
    original_rubric = trials.load_rubric()[variant_rubric["wording_variant_of"]]
    assert finding["category"] == original_rubric["expected_category"]
    assert finding["evidence"] == {
        "line_start": 1,
        "line_end": 1,
        "text": trials.load_prompts()[trial_id]["candidate"],
    }
    valid, reason = trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )
    assert valid, reason


@pytest.mark.parametrize("trial_id", trials.DEFAULT_TRIAL_IDS[18:])
def test_corrected_cases_are_clear_new_artifacts(trial_id: str) -> None:
    case = _case(trial_id)
    prompt, rubric = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    link = trials.resolution_link(
        original_trial_id=rubric["resolution_of"],
        candidate_hash=trials.candidate_sha256(
            trials.load_prompts()[rubric["resolution_of"]]["candidate"]
        ),
        report_hash="b" * 64,
        category=trials.load_rubric()[rubric["resolution_of"]]["expected_category"],
    )
    case = TrialCase(
        case.trial_id,
        (prompt, rubric),
        case.candidate,
        {"resolution": link},
    )
    valid, reason = trials.validate_verdict(
        _verdict(case), case=case, report=_report(case)
    )
    assert valid, reason


def test_verdict_fails_closed_for_hash_category_and_span_errors() -> None:
    case = _case("missing-uncertainty")
    prompt, _ = cast(tuple[dict[str, str], dict[str, Any]], case.context)
    candidate = prompt["candidate"]
    verdict = _verdict(case, findings=[_finding(case)])
    verdict["candidate_sha256"] = "0" * 64
    assert not trials.validate_verdict(verdict, case=case, report=_report(case))[0]
    verdict = _verdict(case, findings=[{**_finding(case), "category": "confounding"}])
    assert not trials.validate_verdict(verdict, case=case, report=_report(case))[0]
    finding = _finding(case)
    finding["evidence"]["text"] = "wrong span"
    assert not trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )[0]
    for malformed in (
        {"line_start": True, "line_end": 1, "text": candidate},
        {"line_start": 0, "line_end": 1, "text": candidate},
        {"line_start": 1, "line_end": 2, "text": candidate},
    ):
        finding = {**_finding(case), "evidence": malformed}
        assert not trials.validate_verdict(
            _verdict(case, findings=[finding]), case=case, report=_report(case)
        )[0]
    duplicate = _finding(case)
    duplicate["reason"] = "A different reason."
    assert not trials.validate_verdict(
        _verdict(case, findings=[_finding(case), duplicate]),
        case=case,
        report=_report(case),
    )[0]


def test_verdict_joins_exact_inclusive_candidate_lines() -> None:
    original = _case("missing-uncertainty")
    _, rubric = cast(tuple[dict[str, str], dict[str, Any]], original.context)
    candidate = (
        "Metric context is stated.\nVariability is omitted.\nA limitation follows."
    )
    prompt = {
        "id": "multiline-uncertainty",
        "author_id": "author-multiline",
        "task": f"Review only missing uncertainty.\n\nCANDIDATE:\n{candidate}",
        "candidate": candidate,
    }
    case = TrialCase(
        "multiline-uncertainty",
        (prompt, rubric),
        trials._candidate_provenance(
            candidate=candidate,
            author_id=prompt["author_id"],
            trial_id=prompt["id"],
        ),
    )
    finding = {
        **_finding(case),
        "evidence": {
            "line_start": 2,
            "line_end": 3,
            "text": "Variability is omitted.\nA limitation follows.",
        },
    }
    valid, reason = trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )
    assert valid, reason
    finding["evidence"]["text"] = "Variability is omitted.A limitation follows."
    assert not trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )[0]


@pytest.mark.parametrize("severity", ["low", "critical"])
def test_verdict_rejects_severity_outside_attested_bounds(severity: str) -> None:
    case = _case("missing-uncertainty")
    finding = {**_finding(case), "severity": severity}
    valid, reason = trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )
    assert not valid
    assert "attested bounds" in reason


@pytest.mark.parametrize("severity", ["medium", "high"])
def test_verdict_accepts_severity_within_attested_bounds(severity: str) -> None:
    case = _case("missing-uncertainty")
    finding = {**_finding(case), "severity": severity}
    valid, reason = trials.validate_verdict(
        _verdict(case, findings=[finding]), case=case, report=_report(case)
    )
    assert valid, reason


def test_verdict_requires_clear_equivalence_unique_findings_and_provenance() -> None:
    case = _case("restrained-abstract")
    verdict = _verdict(case)
    verdict["outcome"]["clear"] = False
    assert not trials.validate_verdict(verdict, case=case, report=_report(case))[0]
    assert not trials.validate_verdict(verdict, case=case, report={})[0]
    assert not trials.validate_verdict(
        verdict,
        case=case,
        report=_report(case, reviewer_id="fixture-author:author-positive-abstract"),
    )[0]
    forged_author = _report(case)
    forged_author["candidate"]["author"]["canonical"] = "fixture-author:other"
    assert not trials.validate_verdict(verdict, case=case, report=forged_author)[0]


def test_correct_hidden_verifier_cannot_rescue_bad_primary_response() -> None:
    case = _case("missing-uncertainty")
    bad_primary = _verdict(case)
    valid, reason = trials.validate_adjudication(
        _hidden_pass(case),
        case=case,
        report=_adjudication_report(case, bad_primary),
        rubric_commit="rubric-commit",
    )
    assert not valid
    assert "primary review is invalid" in reason


def test_adjudication_requires_correct_primary_and_matching_identity() -> None:
    case = _case("missing-uncertainty")
    primary = _verdict(case, findings=[_finding(case)])
    valid, reason = trials.validate_adjudication(
        _hidden_pass(case),
        case=case,
        report=_adjudication_report(case, primary),
        rubric_commit="rubric-commit",
    )
    assert valid, reason
    wrong = _hidden_pass(case)
    wrong["candidate_sha256"] = "0" * 64
    assert not trials.validate_adjudication(
        wrong,
        case=case,
        report=_adjudication_report(case, primary),
        rubric_commit="rubric-commit",
    )[0]


def test_scientific_event_policy_accepts_complete_empty_stream_only() -> None:
    empty = {
        "bounds": {
            "max_items": harness.EVENT_EVIDENCE_MAX_ITEMS,
            "max_field_chars": harness.EVENT_EVIDENCE_MAX_FIELD_CHARS,
            "max_total_chars": harness.EVENT_EVIDENCE_MAX_TOTAL_CHARS,
        },
        "items": [],
        "payload_chars": len("[]"),
        "malformed_lines": 0,
        "invalid_items": 0,
        "dropped_items": 0,
        "field_truncations": 0,
        "truncated": False,
        "read_error": False,
    }
    assert trials.validate_scientific_event_evidence(empty)[0]
    empty["truncated"] = True
    assert not trials.validate_scientific_event_evidence(empty)[0]


def test_duplicate_selected_ids_are_rejected_without_running_codex() -> None:
    adapter = trials.ScientificReviewAdapter()
    fixtures = adapter.load_fixtures(
        {
            trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
            trials.RUBRIC_RELATIVE: trials.RUBRIC_PATH.read_bytes(),
        }
    )
    with pytest.raises(ValueError, match="unique"):
        adapter.select_cases(
            fixtures, selected_ids=("bounded-pilot", "bounded-pilot"), all_cases=False
        )


def test_corrected_resolution_requires_exact_original_artifacts(tmp_path: Path) -> None:
    adapter = trials.ScientificReviewAdapter()
    fixtures = adapter.load_fixtures(
        {
            trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
            trials.RUBRIC_RELATIVE: trials.RUBRIC_PATH.read_bytes(),
        }
    )
    original_id = "missing-uncertainty"
    corrected_id = "missing-uncertainty-corrected"
    original_report = tmp_path / "report.json"
    original_bytes = b'{"trial_id":"missing-uncertainty"}\n'
    original_report.write_bytes(original_bytes)
    report_hash = hashlib.sha256(original_bytes).hexdigest()
    valid_link = trials.resolution_link(
        original_trial_id=original_id,
        candidate_hash=trials.candidate_sha256(
            trials.load_prompts()[original_id]["candidate"]
        ),
        report_hash=report_hash,
        category="uncertainty",
    )
    selected = trials.ScientificReviewAdapter(
        {corrected_id: valid_link}, {original_id: report_hash}
    ).select_cases(fixtures, selected_ids=(corrected_id,), all_cases=False)
    assert selected[0].adapter_metadata == {"resolution": valid_link}
    for field, forged in (
        ("candidate_sha256", "b" * 64),
        ("report_sha256", "b" * 64),
        ("category", "confounding"),
        ("original_trial_id", "other-original"),
    ):
        forged_link = {**valid_link, field: forged}
        with pytest.raises(ValueError, match="forged"):
            trials.ScientificReviewAdapter(
                {corrected_id: forged_link}, {original_id: report_hash}
            ).select_cases(fixtures, selected_ids=(corrected_id,), all_cases=False)
    with pytest.raises(ValueError, match="malformed"):
        trials.ScientificReviewAdapter(
            {corrected_id: {"report_sha256": report_hash}},
            {original_id: report_hash},
        ).select_cases(fixtures, selected_ids=(corrected_id,), all_cases=False)


def test_run_suite_candidate_seam_hashes_exact_candidate_bytes_not_jsonl(
    tmp_path: Path,
) -> None:
    adapter = trials.ScientificReviewAdapter()
    fixtures = adapter.load_fixtures(
        {
            trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
            trials.RUBRIC_RELATIVE: trials.RUBRIC_PATH.read_bytes(),
        }
    )
    case = adapter.select_cases(
        fixtures, selected_ids=("missing-uncertainty",), all_cases=False
    )[0]
    provenance = _candidate_report(
        case.candidate,
        reviewer=ReviewerProvenance(
            PrincipalIdentity("host-user", "reviewer@host"), "host", 1.0
        ),
    )
    assert provenance is not None
    assert provenance["candidate_sha256"] == trials.candidate_sha256(
        trials.load_prompts()["missing-uncertainty"]["candidate"]
    )
    assert (
        provenance["candidate_sha256"]
        != hashlib.sha256(trials.PROMPTS_PATH.read_bytes()).hexdigest()
    )


def test_run_suite_mocked_execution_preserves_exact_candidate_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = trials.ScientificReviewAdapter()
    fixture_bytes = {
        trials.PROMPTS_RELATIVE: trials.PROMPTS_PATH.read_bytes(),
        trials.RUBRIC_RELATIVE: trials.RUBRIC_PATH.read_bytes(),
    }
    monkeypatch.setattr(
        harness, "attest_evaluator_fixtures", lambda *args, **kwargs: fixture_bytes
    )
    monkeypatch.setattr(
        harness,
        "run_git",
        lambda *args, **kwargs: "head" if args and args[0] == "rev-parse" else "",
    )
    monkeypatch.setattr(harness, "_codex_version", lambda **kwargs: "codex-test")
    monkeypatch.setattr(
        harness,
        "_reviewer_provenance",
        lambda **kwargs: ReviewerProvenance(
            PrincipalIdentity("host-user", "reviewer@host"), "host", 1.0
        ),
    )

    @contextmanager
    def fake_worktree(*args: Any, **kwargs: Any):
        yield tmp_path

    monkeypatch.setattr(harness, "detached_worktree", fake_worktree)

    def fake_run_case(**kwargs: Any) -> dict[str, Any]:
        case = kwargs["case"]
        (kwargs["output_dir"] / case.trial_id).mkdir()
        candidate = _candidate_report(
            case.candidate,
            reviewer=ReviewerProvenance(
                PrincipalIdentity("host-user", "reviewer@host"), "host", 1.0
            ),
        )
        return {
            "trial_id": case.trial_id,
            "returncode": 0,
            "timed_out": False,
            "checkout_clean_after": True,
            "event_evidence": {"items": []},
            "candidate": candidate,
        }

    monkeypatch.setattr(harness, "_run_case", fake_run_case)
    monkeypatch.setattr(
        harness,
        "_run_case_verifier",
        lambda **kwargs: {"passed": True, "reason": "ok", "verdict": {}},
    )
    result = trials.run_suite(
        harness.SuiteSpec(
            tested_ref="HEAD",
            rubric_ref="HEAD",
            identity=harness.SuiteIdentity("science", "dirty", "science-"),
            fixture_paths=trials.EVALUATOR_FIXTURE_PATHS,
            output_root=tmp_path / "out",
            trial_schema=trials.VERDICT_SCHEMA,
            verifier_schema=trials.ADJUDICATION_SCHEMA,
            selected_ids=("missing-uncertainty",),
            require_candidate_provenance=True,
            require_execution_evidence=False,
            root=tmp_path,
        ),
        adapter,
    )
    assert result.reports[0]["candidate"][
        "candidate_sha256"
    ] == trials.candidate_sha256(
        trials.load_prompts()["missing-uncertainty"]["candidate"]
    )


def test_schema_is_strict_and_has_no_release_or_mutation_state() -> None:
    schema = json.loads(trials.VERDICT_SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"trial_id", "candidate_sha256", "outcome"}
    assert "uniqueItems" not in json.dumps(schema)
    # Structured-output schemas omit uniqueness; validate_verdict enforces it.
    evidence = schema["properties"]["outcome"]["properties"]["findings"]["items"][
        "properties"
    ]["evidence"]
    assert evidence["additionalProperties"] is False
    assert set(evidence["required"]) == {"line_start", "line_end", "text"}
    assert set(evidence["properties"]) == {"line_start", "line_end", "text"}
    serialized = json.dumps(schema).lower()
    for forbidden in ("maturity", "release", "approval", "mutation", "finding_id"):
        assert forbidden not in serialized
    adjudication = json.loads(trials.ADJUDICATION_SCHEMA.read_text(encoding="utf-8"))
    assert adjudication["additionalProperties"] is False
    assert set(adjudication["required"]) == {
        "trial_id",
        "candidate_sha256",
        "tested_commit",
        "rubric_commit",
        "verdict",
        "reason",
    }
    assert set(adjudication["properties"]["verdict"]["enum"]) == {"pass", "fail"}


def test_resolution_links_use_original_trial_and_artifact_hashes_not_finding_ids() -> (
    None
):
    link = trials.resolution_link(
        original_trial_id="missing-uncertainty",
        candidate_hash="a" * 64,
        report_hash="b" * 64,
        category="uncertainty",
    )
    assert set(link) == {
        "original_trial_id",
        "candidate_sha256",
        "report_sha256",
        "category",
    }
    with pytest.raises(ValueError):
        trials.resolution_link(
            original_trial_id="missing-uncertainty",
            candidate_hash="a" * 64,
            report_hash="not-a-hash",
            category="uncertainty",
        )
