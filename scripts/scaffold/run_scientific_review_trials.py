#!/usr/bin/env python3
"""Run bounded, advisory scientific-review trials through the shared harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, cast

from trial_harness import (
    CandidateProvenance,
    PrincipalIdentity,
    SuiteIdentity,
    SuiteSpec,
    TrialCase,
    run_suite,
)
import trial_harness as harness

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_RELATIVE = Path("scripts/scaffold/fixtures/scientific_review_prompts.jsonl")
RUBRIC_RELATIVE = Path("scripts/scaffold/fixtures/scientific_review_rubric.json")
SCHEMA_RELATIVE = Path("scripts/scaffold/schemas/scientific_review_verdict.schema.json")
ADJUDICATION_SCHEMA_RELATIVE = Path(
    "scripts/scaffold/schemas/scientific_review_adjudication.schema.json"
)
PROMPTS_PATH = ROOT / PROMPTS_RELATIVE
RUBRIC_PATH = ROOT / RUBRIC_RELATIVE
VERDICT_SCHEMA = ROOT / SCHEMA_RELATIVE
ADJUDICATION_SCHEMA = ROOT / ADJUDICATION_SCHEMA_RELATIVE
EVALUATOR_FIXTURE_PATHS = (PROMPTS_RELATIVE, RUBRIC_RELATIVE)
DEFAULT_TRIAL_IDS = (
    "seminar-uncontrolled-ablation",
    "actor-oracle-leakage",
    "invalidity-as-utility",
    "pilot-escalation",
    "pseudoreplication",
    "missing-uncertainty",
    "planned-tense-drift",
    "restrained-abstract",
    "hard-mask-semantics",
    "actor-oracle-separation",
    "bounded-pilot",
    "seminar-uncontrolled-ablation-variant",
    "actor-oracle-leakage-variant",
    "invalidity-as-utility-variant",
    "pilot-escalation-variant",
    "pseudoreplication-variant",
    "missing-uncertainty-variant",
    "planned-tense-drift-variant",
    "seminar-uncontrolled-ablation-corrected",
    "actor-oracle-leakage-corrected",
    "invalidity-as-utility-corrected",
    "pilot-escalation-corrected",
    "pseudoreplication-corrected",
    "missing-uncertainty-corrected",
    "planned-tense-drift-corrected",
)
CATEGORIES = {
    "confounding",
    "actor_oracle_leakage",
    "invalidity_utility",
    "claim_escalation",
    "experimental_units",
    "uncertainty",
    "implementation_status",
}
SEVERITIES = {"low", "medium", "high", "critical"}
SEVERITY_RANK = {
    severity: rank
    for rank, severity in enumerate(("low", "medium", "high", "critical"))
}


def _source_bytes(source: bytes | Path) -> bytes:
    return source if isinstance(source, bytes) else source.read_bytes()


def load_prompts(source: bytes | Path = PROMPTS_PATH) -> dict[str, dict[str, str]]:
    prompts: dict[str, dict[str, str]] = {}
    for line_number, line in enumerate(
        _source_bytes(source).decode("utf-8").splitlines(), 1
    ):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"prompt line {line_number}: invalid JSON") from error
        if not isinstance(record, dict) or set(record) != {
            "id",
            "author_id",
            "task",
            "candidate",
        }:
            raise ValueError(f"prompt line {line_number}: malformed prompt")
        if not all(isinstance(record[key], str) and record[key] for key in record):
            raise ValueError(
                f"prompt line {line_number}: fields must be non-empty strings"
            )
        trial_id = record["id"]
        if trial_id in prompts:
            raise ValueError(f"duplicate prompt id {trial_id!r}")
        if record["candidate"] not in record["task"]:
            raise ValueError(f"prompt {trial_id!r}: task must contain candidate")
        prompts[trial_id] = cast(dict[str, str], record)
    if not prompts:
        raise ValueError("scientific-review prompts are empty")
    return prompts


def load_rubric(source: bytes | Path = RUBRIC_PATH) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(_source_bytes(source).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError("scientific-review rubric is malformed") from error
    fixtures = data.get("fixtures") if isinstance(data, dict) else None
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("rubric fixtures must be a non-empty list")
    rubric: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict) or set(fixture) != {
            "id",
            "case_kind",
            "source_id",
            "expected_category",
            "severity_min",
            "severity_max",
            "wording_variant_of",
            "resolution_of",
            "related_ids",
        }:
            raise ValueError("rubric fixture has an unsupported shape")
        trial_id = fixture["id"]
        if not isinstance(trial_id, str) or not trial_id or trial_id in rubric:
            raise ValueError("rubric fixture IDs must be unique non-empty strings")
        category = fixture["expected_category"]
        severity_min = fixture["severity_min"]
        severity_max = fixture["severity_max"]
        if category is not None and category not in CATEGORIES:
            raise ValueError(f"rubric {trial_id}: category is not closed")
        if fixture["case_kind"] not in {"original", "variant", "corrected", "positive"}:
            raise ValueError(f"rubric {trial_id}: case kind is closed")
        expects_finding = fixture["case_kind"] in {"original", "variant"}
        if expects_finding != (category is not None):
            raise ValueError(f"rubric {trial_id}: category does not match case kind")
        if expects_finding:
            if severity_min not in SEVERITIES or severity_max not in SEVERITIES:
                raise ValueError(f"rubric {trial_id}: severity bounds are not closed")
            if SEVERITY_RANK[severity_min] > SEVERITY_RANK[severity_max]:
                raise ValueError(f"rubric {trial_id}: severity bounds are reversed")
        elif severity_min is not None or severity_max is not None:
            raise ValueError(f"rubric {trial_id}: clear case has severity bounds")
        if not isinstance(fixture["source_id"], str) or not fixture["source_id"]:
            raise ValueError(f"rubric {trial_id}: source ID is required")
        if not isinstance(fixture["related_ids"], list) or not all(
            isinstance(item, str) and item for item in fixture["related_ids"]
        ):
            raise ValueError(f"rubric {trial_id}: related IDs are malformed")
        for field in ("wording_variant_of", "resolution_of"):
            if fixture[field] is not None and not isinstance(fixture[field], str):
                raise ValueError(f"rubric {trial_id}: {field} is malformed")
        rubric[trial_id] = fixture
    return rubric


def candidate_sha256(candidate: str) -> str:
    return hashlib.sha256(candidate.encode("utf-8")).hexdigest()


def resolution_link(
    *, original_trial_id: str, candidate_hash: str, report_hash: str, category: str
) -> dict[str, str]:
    """Identify a corrected review by immutable artifacts, never a finding ID."""
    if category not in CATEGORIES or not original_trial_id:
        raise ValueError("resolution requires an original trial ID and closed category")
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
        for value in (candidate_hash, report_hash)
    ):
        raise ValueError("resolution requires exact SHA-256 artifact hashes")
    return {
        "original_trial_id": original_trial_id,
        "candidate_sha256": candidate_hash,
        "report_sha256": report_hash,
        "category": category,
    }


def validate_scientific_event_evidence(evidence: Any) -> tuple[bool, str]:
    """Use the shared bounded validator with execution evidence optional."""
    return harness.validate_event_evidence(evidence, require_execution_evidence=False)


def _context(
    case: TrialCase,
) -> tuple[dict[str, str], dict[str, Any]]:
    return cast(tuple[dict[str, str], dict[str, Any]], case.context)


def _resolution_metadata(case: TrialCase) -> dict[str, str] | None:
    metadata = case.adapter_metadata
    if metadata is None:
        return None
    if not isinstance(metadata, Mapping) or set(metadata) != {"resolution"}:
        return None
    resolution = metadata["resolution"]
    if not isinstance(resolution, dict) or set(resolution) != {
        "original_trial_id",
        "candidate_sha256",
        "report_sha256",
        "category",
    }:
        return None
    if not all(isinstance(value, str) and value for value in resolution.values()):
        return None
    return cast(dict[str, str], resolution)


def _candidate_provenance(
    *, candidate: str, author_id: str, trial_id: str
) -> CandidateProvenance:
    values: dict[str, Any] = {
        "candidate_bytes": candidate.encode("utf-8"),
        "author": PrincipalIdentity("fixture-author", author_id),
        "expected_sha256": candidate_sha256(candidate),
        "source_locator": f"{PROMPTS_RELATIVE}:{trial_id}",
    }
    return CandidateProvenance(**values)


def _trial_case(
    *,
    trial_id: str,
    context: tuple[dict[str, str], dict[str, Any]],
    candidate: CandidateProvenance,
    resolution: dict[str, str] | None,
) -> TrialCase:
    return TrialCase(
        trial_id=trial_id,
        context=context,
        candidate=candidate,
        adapter_metadata={"resolution": resolution} if resolution else None,
    )


def build_trial_prompt(case: TrialCase) -> str:
    prompt, _ = _context(case)
    return (
        f"{prompt['task']}\n\nThe schema trial_id must be exactly {case.trial_id!r}. "
        "The exact candidate SHA-256 is "
        f"{candidate_sha256(prompt['candidate'])}. Cite evidence with an exact "
        "candidate-relative 1-based inclusive line span. Return at most one finding: "
        "the single most material issue requested by the task. Return only the "
        "strict schema; return clear when no requested issue applies."
    )


def _finding_key(finding: Mapping[str, Any]) -> str:
    return json.dumps(finding, sort_keys=True, separators=(",", ":"))


def validate_verdict(
    payload: object,
    *,
    case: TrialCase,
    report: Mapping[str, Any],
) -> tuple[bool, str]:
    prompt, rubric = _context(case)
    if case.candidate is None or case.candidate.expected_sha256 != candidate_sha256(
        prompt["candidate"]
    ):
        return False, "typed candidate provenance does not match candidate bytes"
    if not isinstance(payload, dict) or set(payload) != {
        "trial_id",
        "candidate_sha256",
        "outcome",
    }:
        return False, "verdict has an unsupported shape"
    expected_hash = candidate_sha256(prompt["candidate"])
    if (
        payload.get("trial_id") != case.trial_id
        or payload.get("candidate_sha256") != expected_hash
    ):
        return False, "candidate identity or trial ID mismatch"
    outcome = payload.get("outcome")
    if not isinstance(outcome, dict) or set(outcome) != {"clear", "findings"}:
        return False, "outcome is malformed"
    findings = outcome.get("findings")
    if not isinstance(outcome.get("clear"), bool) or not isinstance(findings, list):
        return False, "outcome fields are malformed"
    if outcome["clear"] != (len(findings) == 0):
        return False, "clear must be equivalent to findings being empty"
    keys = [_finding_key(finding) for finding in findings if isinstance(finding, dict)]
    if len(keys) != len(findings) or len(set(keys)) != len(keys):
        return False, "findings must be unique objects"
    expected_category = rubric["expected_category"]
    if expected_category is None and findings:
        return False, "positive control has a finding"
    if expected_category is not None:
        if len(findings) != 1 or findings[0].get("category") != expected_category:
            return False, "finding misses the intended semantic category"
        severity = findings[0].get("severity")
        severity_min = rubric["severity_min"]
        severity_max = rubric["severity_max"]
        if (
            severity not in SEVERITY_RANK
            or severity_min not in SEVERITY_RANK
            or severity_max not in SEVERITY_RANK
            or not (
                SEVERITY_RANK[severity_min]
                <= SEVERITY_RANK[severity]
                <= SEVERITY_RANK[severity_max]
            )
        ):
            return False, "finding severity is outside the attested bounds"
    categories = [finding.get("category") for finding in findings]
    if len(categories) != len(set(categories)):
        return False, "finding categories must be unique"
    for finding in findings:
        evidence = finding.get("evidence")
        if not isinstance(evidence, dict) or set(evidence) != {
            "line_start",
            "line_end",
            "text",
        }:
            return False, "finding evidence span is malformed"
        line_start = evidence["line_start"]
        line_end = evidence["line_end"]
        text = evidence["text"]
        if (
            not isinstance(line_start, int)
            or isinstance(line_start, bool)
            or not isinstance(line_end, int)
            or isinstance(line_end, bool)
        ):
            return False, "finding line bounds are malformed"
        candidate_lines = prompt["candidate"].splitlines()
        if (
            line_start < 1
            or line_end < line_start
            or line_end > len(candidate_lines)
            or text != "\n".join(candidate_lines[line_start - 1 : line_end])
        ):
            return (
                False,
                "finding evidence is not an exact candidate-relative line span",
            )
        for field in ("reason", "impact", "action"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                return False, f"finding {field} is missing"
    persisted_candidate = report.get("candidate")
    persisted_reviewer = report.get("reviewer")
    if not isinstance(persisted_candidate, Mapping) or not isinstance(
        persisted_reviewer, Mapping
    ):
        return False, "persisted candidate/reviewer provenance is missing"
    persisted_author = persisted_candidate.get("author")
    author_canonical = (
        persisted_author.get("canonical")
        if isinstance(persisted_author, Mapping)
        else None
    )
    reviewer_canonical = persisted_reviewer.get("canonical")
    if author_canonical != case.candidate.author.canonical():
        return False, "persisted candidate author provenance does not match case"
    if not isinstance(reviewer_canonical, str) or not reviewer_canonical:
        return False, "persisted reviewer provenance is missing"
    if reviewer_canonical == author_canonical:
        return False, "author and reviewer identities must differ"
    if rubric["case_kind"] == "corrected":
        resolution = _resolution_metadata(case)
        if resolution is None:
            return False, "corrected case lacks a persisted original resolution link"
        if resolution["original_trial_id"] != rubric["resolution_of"]:
            return False, "resolution does not identify the original trial"
        if resolution["category"] not in CATEGORIES:
            return False, "resolution category is not closed"
        if any(
            len(resolution[field]) != 64
            or any(char not in "0123456789abcdef" for char in resolution[field])
            for field in ("candidate_sha256", "report_sha256")
        ):
            return False, "resolution artifact hashes are malformed"
    return True, "scientific review matches the closed rubric"


def _primary_response(report: Mapping[str, Any]) -> tuple[object | None, str]:
    response = report.get("trial_response")
    if not isinstance(response, dict) or set(response) != {
        "label",
        "format",
        "content",
        "max_chars",
        "truncated",
    }:
        return None, "primary response wrapper is malformed"
    if (
        response["label"] != "untrusted_trial_response"
        or response["format"] != "json"
        or response["truncated"] is not False
        or not isinstance(response["content"], str)
        or not isinstance(response["max_chars"], int)
        or response["max_chars"] != harness.TRIAL_RESPONSE_MAX_CHARS
        or len(response["content"]) > harness.TRIAL_RESPONSE_MAX_CHARS
    ):
        return None, "primary response is missing, truncated, or not JSON"
    try:
        return json.loads(response["content"]), "primary response parsed"
    except json.JSONDecodeError:
        return None, "primary response is not JSON"


def validate_adjudication(
    payload: object,
    *,
    case: TrialCase,
    report: Mapping[str, Any],
    rubric_commit: str,
) -> tuple[bool, str]:
    """Accept hidden pass only after independently validating the primary JSON."""
    primary, reason = _primary_response(report)
    if primary is None:
        return False, reason
    primary_valid, primary_reason = validate_verdict(primary, case=case, report=report)
    if not primary_valid:
        return False, f"primary review is invalid: {primary_reason}"
    prompt, _ = _context(case)
    tested_commit = report.get("tested_commit")
    if not isinstance(tested_commit, str):
        return False, "adjudication tested commit is missing"
    if not isinstance(payload, dict) or set(payload) != {
        "trial_id",
        "candidate_sha256",
        "tested_commit",
        "rubric_commit",
        "verdict",
        "reason",
    }:
        return False, "adjudication is malformed"
    if (
        payload["trial_id"] != case.trial_id
        or payload["candidate_sha256"] != candidate_sha256(prompt["candidate"])
        or payload["tested_commit"] != tested_commit
        or payload["rubric_commit"] != rubric_commit
        or payload["verdict"] != "pass"
        or not isinstance(payload["reason"], str)
        or not payload["reason"].strip()
    ):
        return False, "adjudication identity or semantic verdict does not match"
    return True, "primary review is correct and hidden adjudication passes"


def build_verifier_prompt(
    case: TrialCase, report: Mapping[str, Any], rubric_commit: str
) -> str:
    prompt, rubric = _context(case)
    resolution = _resolution_metadata(case)
    return json.dumps(
        {
            "instruction": "Judge the bounded untrusted primary response against the exact candidate and hidden rubric. Return only the strict adjudication schema. Do not rewrite, correct, or synthesize a primary finding.",
            "rubric_commit": rubric_commit,
            "tested_commit": report.get("tested_commit"),
            "trial_id": case.trial_id,
            "hidden_rubric": rubric,
            "candidate": prompt["candidate"],
            "candidate_sha256": candidate_sha256(prompt["candidate"]),
            "trial_response": report.get("trial_response"),
            "resolution": resolution,
        },
        sort_keys=True,
    )


class ScientificReviewAdapter:
    """Keep scientific policy behind the shared suite lifecycle seam."""

    def __init__(
        self,
        resolution_links: Mapping[str, dict[str, str]] | None = None,
        original_report_hashes: Mapping[str, str] | None = None,
    ) -> None:
        self.resolution_links = dict(resolution_links or {})
        self.original_report_hashes = dict(original_report_hashes or {})

    def load_fixtures(
        self, fixture_bytes: Mapping[Path, bytes]
    ) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]]:
        prompts = load_prompts(fixture_bytes[PROMPTS_RELATIVE])
        rubric = load_rubric(fixture_bytes[RUBRIC_RELATIVE])
        if set(prompts) != set(rubric):
            raise ValueError("scientific-review prompt and rubric IDs differ")
        for trial_id, fixture in rubric.items():
            source_id = fixture["source_id"]
            if source_id not in prompts:
                raise ValueError(f"rubric {trial_id}: source ID dangles")
            if any(related_id not in rubric for related_id in fixture["related_ids"]):
                raise ValueError(f"rubric {trial_id}: related ID dangles")
            if fixture["case_kind"] == "variant":
                if fixture["wording_variant_of"] != source_id:
                    raise ValueError(
                        f"rubric {trial_id}: variant link is not reciprocal"
                    )
                if trial_id not in rubric[source_id]["related_ids"]:
                    raise ValueError(f"rubric {trial_id}: original lacks variant link")
                if (
                    fixture["severity_min"],
                    fixture["severity_max"],
                ) != (
                    rubric[source_id]["severity_min"],
                    rubric[source_id]["severity_max"],
                ):
                    raise ValueError(
                        f"rubric {trial_id}: variant severity bounds differ"
                    )
            elif fixture["case_kind"] == "corrected":
                if fixture["resolution_of"] != source_id:
                    raise ValueError(f"rubric {trial_id}: correction link is malformed")
                if trial_id not in rubric[source_id]["related_ids"]:
                    raise ValueError(
                        f"rubric {trial_id}: original lacks correction link"
                    )
            elif (
                fixture["wording_variant_of"] is not None
                or fixture["resolution_of"] is not None
            ):
                raise ValueError(f"rubric {trial_id}: inverse link has wrong case kind")
            elif fixture["case_kind"] == "original":
                if (
                    fixture["wording_variant_of"] is not None
                    or fixture["resolution_of"] is not None
                ):
                    raise ValueError(f"rubric {trial_id}: original has inverse link")
            elif fixture["expected_category"] is not None:
                raise ValueError(f"rubric {trial_id}: positive case has a category")
        return prompts, rubric

    def select_cases(
        self, fixtures: object, *, selected_ids: tuple[str, ...], all_cases: bool
    ) -> tuple[TrialCase, ...]:
        prompts, rubric = cast(
            tuple[dict[str, dict[str, str]], dict[str, dict[str, Any]]], fixtures
        )
        selected = tuple(prompts) if all_cases else selected_ids
        if len(set(selected)) != len(selected):
            raise ValueError("scientific-review trial IDs must be unique")
        unknown = sorted(set(selected) - set(prompts))
        if unknown:
            raise ValueError(f"unknown scientific-review trial IDs: {unknown}")
        cases: list[TrialCase] = []
        for trial_id in selected:
            prompt, fixture = prompts[trial_id], rubric[trial_id]
            resolution = self.resolution_links.get(trial_id)
            if fixture["case_kind"] == "corrected":
                source_id = fixture["resolution_of"]
                if not isinstance(resolution, dict) or set(resolution) != {
                    "original_trial_id",
                    "candidate_sha256",
                    "report_sha256",
                    "category",
                }:
                    raise ValueError(
                        f"corrected case {trial_id}: resolution metadata is malformed"
                    )
                original = prompts[source_id]
                expected_report_hash = self.original_report_hashes.get(source_id)
                if (
                    resolution["original_trial_id"] != source_id
                    or resolution["candidate_sha256"]
                    != candidate_sha256(original["candidate"])
                    or resolution["category"] != rubric[source_id]["expected_category"]
                    or expected_report_hash is None
                    or resolution["report_sha256"] != expected_report_hash
                ):
                    raise ValueError(
                        f"corrected case {trial_id}: resolution metadata is forged"
                    )
            candidate = _candidate_provenance(
                candidate=prompt["candidate"],
                author_id=prompt["author_id"],
                trial_id=trial_id,
            )
            cases.append(
                _trial_case(
                    trial_id=trial_id,
                    context=(prompt, fixture),
                    candidate=candidate,
                    resolution=resolution,
                )
            )
        return tuple(cases)

    def build_trial_prompt(self, case: TrialCase) -> str:
        return build_trial_prompt(case)

    def build_verifier_prompt(
        self, case: TrialCase, report: Mapping[str, Any], rubric_commit: str
    ) -> str:
        return build_verifier_prompt(case, report, rubric_commit)

    def validate_verdict(
        self,
        case: TrialCase,
        payload: object,
        report: Mapping[str, Any],
        rubric_commit: str,
    ) -> tuple[bool, str]:
        return validate_adjudication(
            payload, case=case, report=report, rubric_commit=rubric_commit
        )

    def trial_passed(self, report: Mapping[str, Any]) -> bool:
        return bool(report.get("adjudication", {}).get("passed", False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--id", action="append", dest="ids")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--effort")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=600)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = tuple(args.ids or DEFAULT_TRIAL_IDS)
    if args.list:
        print("\n".join(selected))
        return 0
    identity = SuiteIdentity(
        name="scientific-review",
        dirty_root_message="commit the candidate before scientific-review trials",
        worktree_prefix="aria-scientific-review-",
    )
    correction_ids = tuple(
        trial_id for trial_id in selected if trial_id.endswith("-corrected")
    )
    initial_ids = tuple(
        trial_id for trial_id in selected if trial_id not in correction_ids
    )
    if not correction_ids:
        initial_ids = selected
    try:
        output_root = ROOT / ".agents" / "work" / "scientific-review-trials"
        initial = run_suite(
            SuiteSpec(
                tested_ref=args.head,
                rubric_ref="HEAD",
                identity=identity,
                fixture_paths=EVALUATOR_FIXTURE_PATHS,
                output_root=output_root / "initial",
                trial_schema=VERDICT_SCHEMA,
                verifier_schema=ADJUDICATION_SCHEMA,
                selected_ids=initial_ids,
                model=args.model,
                effort=args.effort,
                jobs=args.jobs,
                timeout_seconds=args.timeout,
                require_candidate_provenance=True,
                require_execution_evidence=False,
            ),
            ScientificReviewAdapter(),
        )
        if not correction_ids:
            return initial.exit_code
        if initial.output_dir is None or initial.exit_code != 0:
            raise ValueError(
                "corrected cases require a successful persisted original review"
            )
        rubric = load_rubric()
        links: dict[str, dict[str, str]] = {}
        original_report_hashes: dict[str, str] = {}
        for corrected_id in correction_ids:
            original_id = rubric[corrected_id]["resolution_of"]
            original_report = initial.output_dir / original_id / "report.json"
            if not original_report.is_file():
                raise ValueError(f"missing persisted original report for {original_id}")
            original_hash = hashlib.sha256(original_report.read_bytes()).hexdigest()
            original_report_hashes[original_id] = original_hash
            prompt = load_prompts()[original_id]
            links[corrected_id] = resolution_link(
                original_trial_id=original_id,
                candidate_hash=candidate_sha256(prompt["candidate"]),
                report_hash=original_hash,
                category=rubric[original_id]["expected_category"],
            )
        corrected = run_suite(
            SuiteSpec(
                tested_ref=args.head,
                rubric_ref="HEAD",
                identity=identity,
                fixture_paths=EVALUATOR_FIXTURE_PATHS,
                output_root=output_root / "corrected",
                trial_schema=VERDICT_SCHEMA,
                verifier_schema=ADJUDICATION_SCHEMA,
                selected_ids=correction_ids,
                model=args.model,
                effort=args.effort,
                jobs=args.jobs,
                timeout_seconds=args.timeout,
                require_candidate_provenance=True,
                require_execution_evidence=False,
            ),
            ScientificReviewAdapter(links, original_report_hashes),
        )
        return max(initial.exit_code, corrected.exit_code)
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    sys.exit(main())
