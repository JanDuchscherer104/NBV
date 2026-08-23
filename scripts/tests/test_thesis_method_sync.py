"""Deterministic WP6 contracts for method/experiment-to-code synchronization."""

from __future__ import annotations

import importlib.util
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METHOD_ROOTS = (
    ROOT / "docs/typst/thesis/sections/04-method",
    ROOT / "docs/typst/thesis/sections/05-experimental-design",
)
METRIC_SURFACES = (
    ROOT
    / "docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ",
    ROOT
    / "docs/typst/thesis/sections/05-experimental-design/05-01-objectives-and-hypotheses.typ",
    ROOT
    / "docs/typst/thesis/sections/05-experimental-design/05-03-policy-comparison-and-failure-interpretation.typ",
)
CANONICAL_METRIC_REFERENCES = (
    "#eqs.entity.endpoint_gain",
    "#eqs.rl.target_root_gain_reward",
    "#eqs.rl.cumulative_target_root_gain",
)
LOCATOR_RE = re.compile(
    r"(?P<path>(?:aria_nbv|tests|docs)/[^:\s]+):(?P<start>\d+)"
    r"(?:-(?P<end>\d+))?"
)
CLAIM_CHECKER_SPEC = importlib.util.spec_from_file_location(
    "check_thesis_claims", ROOT / "scripts/check_thesis_claims.py"
)
assert CLAIM_CHECKER_SPEC and CLAIM_CHECKER_SPEC.loader
CLAIM_CHECKER = importlib.util.module_from_spec(CLAIM_CHECKER_SPEC)
sys.modules["check_thesis_claims"] = CLAIM_CHECKER
CLAIM_CHECKER_SPEC.loader.exec_module(CLAIM_CHECKER)


def _method_files() -> list[Path]:
    return [path for root in METHOD_ROOTS for path in sorted(root.glob("*.typ"))]


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in _method_files())


def _evidence_blocks() -> list[tuple[Path, int, list[str]]]:
    blocks: list[tuple[Path, int, list[str]]] = []
    for path in _method_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        index = 0
        while index < len(lines):
            if lines[index].strip() != "// evidence:":
                index += 1
                continue
            start = index + 1
            index += 1
            body: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("//"):
                body.append(lines[index])
                index += 1
            blocks.append((path, start, body))
    return blocks


def test_implemented_evidence_locators_resolve_to_current_paths_and_lines() -> None:
    locators = [
        match
        for _, _, body in _evidence_blocks()
        for line in body
        for match in LOCATOR_RE.finditer(line)
    ]
    assert locators, "implemented method surface must contain evidence locators"
    for match in locators:
        path = ROOT / match.group("path")
        start = int(match.group("start"))
        end = int(match.group("end") or match.group("start"))
        assert path.is_file(), path
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= start <= end <= line_count, (path, start, end, line_count)


def test_implemented_evidence_blocks_link_to_code_owner_and_tests() -> None:
    for path, _, body in _evidence_blocks():
        locators = [match for line in body for match in LOCATOR_RE.finditer(line)]
        assert any(
            match.group("path").startswith("aria_nbv/aria_nbv/") for match in locators
        ), path
        assert any(
            match.group("path").startswith("aria_nbv/tests/") for match in locators
        ), path
        assert all((ROOT / match.group("path")).is_file() for match in locators), path


def test_every_method_evidence_block_is_adjacent_to_implemented_factual_prose() -> None:
    for path, marker_line, _ in _evidence_blocks():
        lines = path.read_text(encoding="utf-8").splitlines()
        before = " ".join(lines[: marker_line - 1]).strip()
        after = " ".join(lines[marker_line:]).strip()
        nearby = before[-900:] + " " + after[:900]
        assert re.search(r"\bimplemented\b|\bfactual\b|\bcontract\b", nearby, re.I), (
            path,
            marker_line,
        )


def test_development_only_alternatives_have_no_implemented_evidence_block() -> None:
    for path in _method_files():
        text = path.read_text(encoding="utf-8")
        for block in re.findall(r"#development_only\(\(\) => \[(.*?)\]\)", text, re.S):
            assert "// evidence:" not in block
            # Explicitly negated maturity wording is the required guardrail;
            # a development block may say that an alternative is *not*
            # implemented without promoting it.
            unnegated = re.sub(
                r"\bnone is an implemented\b|\bpresented as implemented\b",
                "",
                block,
                flags=re.I,
            )
            assert not re.search(r"\bimplemented\b", unnegated, re.I)


def test_planned_scorer_alternatives_are_submission_excluded_by_development_only() -> (
    None
):
    scorer = (
        ROOT
        / "docs/typst/thesis/sections/04-method/04-05-finite-candidate-value-model.typ"
    )
    text = scorer.read_text(encoding="utf-8")
    blocks = re.findall(r"#development_only\(\(\) => \[(.*?)\]\)", text, re.S)
    assert blocks, "planned scorer alternatives must have a development_only boundary"
    assert any(
        re.search(r"alternative|development evidence|planned", block, re.I)
        for block in blocks
    )
    assert not re.search(r"#development_only\(\(\) => \[.*?// evidence:", text, re.S)


def _development_only_ranges(text: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start_pattern = re.compile(r"#development_only\(\(\) => \[")
    for match in start_pattern.finditer(text):
        depth = 0
        index = match.start()
        while index < len(text):
            if text[index] == "[":
                depth += 1
            elif text[index] == "]":
                depth -= 1
                if depth == 0:
                    end = text.find(")", index)
                    if end >= 0:
                        ranges.append((match.start(), end + 1))
                    break
            index += 1
    return ranges


def _submission_visible_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    for start, end in reversed(_development_only_ranges(text)):
        text = text[:start] + text[end:]
    return text


def test_submission_visible_method_files_exclude_planned_scorer_state_and_representation_prose() -> (
    None
):
    planned_surface = re.compile(
        r"\bplanned\s+(?:production\s+)?(?:scorer|state|representation)\b|"
        r"\b(?:scorer|state|representation)\s+(?:input|contract|direction|extension)\s+remains\s+planned\b",
        re.I,
    )
    for path in sorted(
        ROOT.joinpath("docs/typst/thesis/sections/04-method").glob("*.typ")
    ):
        match = planned_surface.search(_submission_visible_text(path))
        assert match is None, (path, match.group(0) if match else None)


def test_metric_surfaces_use_canonical_owners_without_exact_equivalence_claim() -> None:
    positive_exact_equivalence = re.compile(
        r"\b(?:exact(?:ly)?\s+equiv(?:alent|alence)|shared[- ]denominator|"
        r"same[- ]denominator)\b",
        re.I,
    )
    for path in METRIC_SURFACES:
        text = path.read_text(encoding="utf-8")
        for owner_reference in CANONICAL_METRIC_REFERENCES:
            assert owner_reference in text, (path, owner_reference)
        for match in positive_exact_equivalence.finditer(text):
            sentence_start = max(
                text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())
            )
            sentence = text[sentence_start + 1 : text.find(".", match.end())]
            assert re.search(
                r"\b(?:no|not|without|does not)\b", sentence, re.I
            ) or not re.search(
                r"\b(?:exact(?:ly)?\s+equiv(?:alent|alence)|shared[- ]denominator|same[- ]denominator)\b",
                sentence,
                re.I,
            ), (
                path,
                match.group(0),
            )


def test_method_contract_covers_actor_oracle_and_distinct_masks() -> None:
    text = _text()
    required = (
        (r"actor/oracle separation", "actor/oracle separation"),
        (r"valid_action_mask.*q_train_mask.*padding", "three distinct masks"),
        (r"all-invalid successor.*no-bootstrap", "all-invalid no-bootstrap"),
    )
    for pattern, description in required:
        assert re.search(pattern, text, re.I | re.S), description


def test_method_contract_covers_support_frame_and_metric_boundaries() -> None:
    text = _text()
    assert re.search(r"finite candidate support|finite support", text, re.I)
    assert re.search(r"frame discipline", text, re.I)
    assert re.search(
        r"does not (?:claim|establish).*scorer invariance|do not authorize.*scorer.*invariance",
        text,
        re.I | re.S,
    )
    assert re.search(r"target-root gain.*additive", text, re.I | re.S)
    assert re.search(
        r"state-relative RRI.*(?:not additive|diagnostic)", text, re.I | re.S
    )


def test_pc_c1_maturity_and_discussion_conclusion_language_remain_bounded() -> None:
    ledger = tomllib.loads(
        (ROOT / "docs/typst/thesis/data/principal-claims.toml").read_text(
            encoding="utf-8"
        )
    )
    claim = next(
        item
        for item in ledger["claims"]
        if item["id"] == "pc-c1-auditable-experiment-contract"
    )
    assert (claim["maturity"], claim["review_state"], claim["release_state"]) == (
        "planned",
        "unreviewed",
        "withheld",
    )
    model = CLAIM_CHECKER.read_principal_claims()
    assert (
        next(item for item in model.claims if item.id == claim["id"]).release_state
        == "withheld"
    )
    for relative in (
        "docs/typst/thesis/sections/07-discussion.typ",
        "docs/typst/thesis/sections/08-conclusion.typ",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "pc-c1-auditable-experiment-contract" in text
        claim_marker = text.index("pc-c1-auditable-experiment-contract")
        nearby = text[max(0, claim_marker - 900) : claim_marker + 900]
        assert re.search(
            r"(?:evidence|results?|substrate).{0,180}\b(?:toward|does not establish|not establish(?:ing)?)\b|"
            r"\b(?:toward|does not establish|not establish(?:ing)?)\b.{0,180}(?:planned claim|claim|contribution)",
            nearby,
            re.I | re.S,
        ), (relative, nearby)
        assert not re.search(
            r"\b(?:this|the evidence|the results?)\s+(?:proves?|establishes?)\s+superiority|"
            r"\b(?:this|the evidence|the results?)\s+performs better\b",
            text,
            re.I,
        )


def test_primary_scorer_is_explicitly_planned_fixed_h() -> None:
    text = _text()
    assert re.search(
        r"primary (?:planned )?(?:scorer|learning objective).*fixed-(?:H|horizon)|planned fixed-H",
        text,
        re.I | re.S,
    )
    assert not re.search(
        r"(?:implemented|current) (?:primary )?(?:scorer|policy)", text, re.I
    )
