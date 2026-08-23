"""Table-driven contract tests for the typed thesis claim ledger."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
from itertools import product
from pathlib import Path
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "check_thesis_claims", ROOT / "scripts/check_thesis_claims.py"
)
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
sys.modules["check_thesis_claims"] = CHECK
SPEC.loader.exec_module(CHECK)
REVISION = "1" * 40


def test_real_ledger_is_typed_and_withheld() -> None:
    model = CHECK.read_principal_claims()
    assert {claim.release_applicability for claim in model.claims} == {
        "required",
        "conditional",
        "non-release",
    }
    assert all(claim.release_state == "withheld" for claim in model.claims)
    assert {claim.outcome for claim in model.claims} == {"missing", "conditional"}


def _fixture(
    tmp_path: Path, *, outcome: str = "missing", release_state: str = "withheld"
) -> tuple[dict[str, Any], Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "surface.typ").write_text(
        "Owner paragraph. <claim-owner:pc-test>\n\n"
        "Falsifier paragraph. <claim-falsifier:pc-test>\n\n"
        "Limitation paragraph. <claim-limitation:pc-test>\n",
        encoding="utf-8",
    )
    (tmp_path / "code.py").write_text("VALUE = 1\n", encoding="utf-8")
    artifact = tmp_path / "result.json"
    artifact.write_text('{"result": "negative"}\n', encoding="utf-8")
    artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    claim: dict[str, Any] = {
        "id": "pc-test",
        "class": "result",
        "rqs": ["rq1"],
        "release_applicability": "required",
        "maturity": "planned",
        "outcome": outcome,
        "review_state": "unreviewed",
        "release_state": release_state,
        "owner": "typst:surface.typ#claim-owner:pc-test",
        "falsifier": "typst:surface.typ#claim-falsifier:pc-test",
        "limitations": ["typst:surface.typ#claim-limitation:pc-test"],
        "evidence": [{"role": "implementation", "locator": "code:code.py"}],
    }
    if release_state == "admissible":
        claim.update(maturity="confirmatory", review_state="approved")
        claim["evidence"] = [
            {
                "role": "empirical",
                "locator": f"artifact:result.json@sha256:{artifact_digest}",
            }
        ]
    return {"schema": CHECK.SCHEMA, "claims": [claim], "receipts": []}, tmp_path


def _accepted(
    root: Path, locator: str = "typst:surface.typ#claim-owner:pc-test"
) -> str:
    parsed = CHECK._locator(locator, root, "test locator", "receipt")
    return CHECK._anchor_slice(parsed, root, "pc-test").accepted_sha256


def _receipt(
    root: Path,
    *,
    rid: str,
    kind: str,
    source: str,
    target: str,
    authentication: str = "github-review",
) -> dict[str, str]:
    return {
        "id": rid,
        "claim_id": "pc-test",
        "kind": kind,
        "from": source,
        "to": target,
        "principal": "github:review-123",
        "authentication": authentication,
        "verdict": "advisory" if kind == "advisory" else target,
        "locator": "typst:surface.typ#claim-owner:pc-test",
        "accepted_sha256": _accepted(root),
        "repository_revision": REVISION,
        "reviewed_at": "2026-08-23T10:00:00Z",
    }


def _promotion_receipts(root: Path) -> list[dict[str, str]]:
    return [
        _receipt(
            root,
            rid="maturity-implemented",
            kind="maturity",
            source="planned",
            target="implemented",
        ),
        _receipt(
            root,
            rid="maturity-pilot",
            kind="maturity",
            source="implemented",
            target="pilot",
        ),
        _receipt(
            root,
            rid="maturity-confirmatory",
            kind="maturity",
            source="pilot",
            target="confirmatory",
        ),
        _receipt(
            root,
            rid="review-approved",
            kind="review",
            source="unreviewed",
            target="approved",
        ),
        _receipt(
            root,
            rid="release-admissible",
            kind="release",
            source="withheld",
            target="admissible",
        ),
    ]


@pytest.mark.parametrize(
    ("outcome", "admissible"),
    [
        ("missing", False),
        ("failed", False),
        ("conditional", False),
        ("completed-negative", True),
        ("confirmatory", True),
    ],
)
def test_outcome_release_boundary(
    tmp_path: Path, outcome: str, admissible: bool
) -> None:
    data, root = _fixture(tmp_path, outcome=outcome, release_state="admissible")
    data["receipts"] = _promotion_receipts(root)
    if admissible:
        model = CHECK.validate_ledger(
            data,
            root,
            receipt_verifier=lambda _attestation: True,
            repository_revision=REVISION,
        )
        assert model.claims[0].release_state == "admissible"
    else:
        with pytest.raises(CHECK.ClaimValidationError, match="admissibility"):
            CHECK.validate_ledger(
                data,
                root,
                receipt_verifier=lambda _attestation: True,
                repository_revision=REVISION,
            )


def test_conditional_and_non_release_claims_remain_withheld(tmp_path: Path) -> None:
    for applicability in ("conditional", "non-release"):
        data, root = _fixture(
            tmp_path / applicability,
            outcome="completed-negative",
            release_state="admissible",
        )
        data["claims"][0]["release_applicability"] = applicability
        data["receipts"] = _promotion_receipts(root)
        with pytest.raises(CHECK.ClaimValidationError, match="admissibility"):
            CHECK.validate_ledger(
                data,
                root,
                receipt_verifier=lambda _attestation: True,
                repository_revision=REVISION,
            )


def test_anchor_roles_canonical_spans_and_code_owners_fail_closed(
    tmp_path: Path,
) -> None:
    data, root = _fixture(tmp_path)
    role_swap = copy.deepcopy(data)
    role_swap["claims"][0]["owner"] = "typst:surface.typ#claim-falsifier:pc-test"
    with pytest.raises(CHECK.ClaimValidationError, match="anchor prefix"):
        CHECK.validate_ledger(role_swap, root)

    prose_code = copy.deepcopy(data)
    prose_code["claims"][0]["evidence"] = [
        {"role": "implementation", "locator": "code:surface.typ"}
    ]
    with pytest.raises(CHECK.ClaimValidationError, match="code owner"):
        CHECK.validate_ledger(prose_code, root)

    (root / "surface.typ").write_text(
        "Same paragraph. <claim-owner:pc-test> <claim-falsifier:pc-test>\n\n"
        "Limitation. <claim-limitation:pc-test>\n",
        encoding="utf-8",
    )
    aliased = copy.deepcopy(data)
    aliased["claims"][0]["falsifier"] = "typst:./surface.typ#claim-falsifier:pc-test"
    with pytest.raises(CHECK.ClaimValidationError, match="distinct canonical slices"):
        CHECK.validate_ledger(aliased, root)


def test_duplicate_anchor_occurrences_on_same_line_are_rejected(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "<claim-owner:pc-test>", "<claim-owner:pc-test> <claim-owner:pc-test>"
        ),
        encoding="utf-8",
    )
    with pytest.raises(CHECK.ClaimValidationError, match="exactly one"):
        CHECK.validate_ledger(data, root)


@pytest.mark.parametrize(
    "commented_anchor",
    [
        "// <claim-owner:pc-test>",
        "/* <claim-owner:pc-test> */",
    ],
)
def test_typst_comment_anchors_do_not_count(
    tmp_path: Path, commented_anchor: str
) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "<claim-owner:pc-test>", commented_anchor
        ),
        encoding="utf-8",
    )

    with pytest.raises(CHECK.ClaimValidationError, match="exactly one"):
        CHECK.validate_ledger(data, root)


def test_typst_string_anchor_does_not_count(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "<claim-owner:pc-test>", '"escaped \\" <claim-owner:pc-test>"'
        ),
        encoding="utf-8",
    )

    with pytest.raises(CHECK.ClaimValidationError, match="exactly one"):
        CHECK.validate_ledger(data, root)


def test_typst_raw_literal_anchor_does_not_count(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "<claim-owner:pc-test>",
            "```one ` two `` <claim-owner:pc-test>```",
        ),
        encoding="utf-8",
    )

    with pytest.raises(CHECK.ClaimValidationError, match="exactly one"):
        CHECK.validate_ledger(data, root)


def test_active_anchor_and_identical_string_literal_count_once(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "<claim-owner:pc-test>",
            '<claim-owner:pc-test> "<claim-owner:pc-test>"',
        ),
        encoding="utf-8",
    )

    assert CHECK.validate_ledger(data, root).claims[0].id == "pc-test"


@pytest.mark.parametrize(
    "literal",
    [
        '"<claim-owner:pc-test>"',
        "```<claim-owner:pc-test>```",
    ],
)
def test_inactive_identical_anchor_bytes_remain_digest_bound(
    tmp_path: Path, literal: str
) -> None:
    data, root = _fixture(tmp_path)
    surface = root / "surface.typ"
    surface.write_text(
        surface.read_text(encoding="utf-8").replace(
            "Owner paragraph. <claim-owner:pc-test>",
            f"Owner paragraph. <claim-owner:pc-test> {literal}",
        ),
        encoding="utf-8",
    )
    expected = hashlib.sha256(f"Owner paragraph.  {literal}\n".encode()).hexdigest()

    assert _accepted(root) == expected


def test_empirical_artifact_cannot_alias_claim_prose_resource(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    thesis_surface = root / "docs/typst/surface.typ"
    thesis_surface.parent.mkdir(parents=True)
    thesis_surface.write_bytes((root / "surface.typ").read_bytes())
    data["claims"][0].update(
        owner="typst:docs/typst/surface.typ#claim-owner:pc-test",
        falsifier="typst:docs/typst/surface.typ#claim-falsifier:pc-test",
        limitations=["typst:docs/typst/surface.typ#claim-limitation:pc-test"],
    )
    surface_digest = hashlib.sha256(thesis_surface.read_bytes()).hexdigest()
    data["claims"][0]["evidence"] = [
        {
            "role": "empirical",
            "locator": f"artifact:docs/typst/surface.typ@sha256:{surface_digest}",
        }
    ]

    with pytest.raises(CHECK.ClaimValidationError, match="claim prose resource"):
        CHECK.validate_ledger(data, root)


def test_empirical_artifact_cannot_alias_another_claims_prose_resource(
    tmp_path: Path,
) -> None:
    data, root = _fixture(tmp_path)
    other_surface = root / "other.typ"
    other_surface.write_text(
        "Other owner. <claim-owner:pc-other>\n\n"
        "Other falsifier. <claim-falsifier:pc-other>\n\n"
        "Other limitation. <claim-limitation:pc-other>\n",
        encoding="utf-8",
    )
    other = copy.deepcopy(data["claims"][0])
    other.update(
        id="pc-other",
        owner="typst:other.typ#claim-owner:pc-other",
        falsifier="typst:other.typ#claim-falsifier:pc-other",
        limitations=["typst:other.typ#claim-limitation:pc-other"],
    )
    digest = hashlib.sha256(other_surface.read_bytes()).hexdigest()
    data["claims"][0]["evidence"] = [
        {
            "role": "empirical",
            "locator": f"artifact:other.typ@sha256:{digest}",
        }
    ]
    data["claims"].append(other)

    with pytest.raises(CHECK.ClaimValidationError, match="claim prose resource"):
        CHECK.validate_ledger(data, root)


def test_spoofed_authentication_label_cannot_promote_without_verifier(
    tmp_path: Path,
) -> None:
    data, root = _fixture(tmp_path)
    data["claims"][0]["maturity"] = "implemented"
    data["receipts"] = [
        _receipt(
            root,
            rid="spoofed-review",
            kind="maturity",
            source="planned",
            target="implemented",
        )
    ]
    with pytest.raises(
        CHECK.ClaimValidationError, match="verified immutable authentication"
    ):
        CHECK.validate_ledger(data, root, repository_revision=REVISION)


def test_non_boolean_verifier_result_fails_closed(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    data["claims"][0]["maturity"] = "implemented"
    data["receipts"] = [
        _receipt(
            root,
            rid="denied-review",
            kind="maturity",
            source="planned",
            target="implemented",
        )
    ]

    with pytest.raises(
        CHECK.ClaimValidationError, match="verified immutable authentication"
    ):
        CHECK.validate_ledger(
            data,
            root,
            receipt_verifier=lambda _attestation: "DENIED",
            repository_revision=REVISION,
        )


def test_verifier_backed_promotion_receives_bound_attestation(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    data["claims"][0]["maturity"] = "implemented"
    data["receipts"] = [
        _receipt(
            root,
            rid="verified-review",
            kind="maturity",
            source="planned",
            target="implemented",
        )
    ]
    seen: list[Any] = []

    def verifier(attestation: Any) -> bool:
        seen.append(attestation)
        return attestation == CHECK.ReceiptAttestation(
            "pc-test",
            "maturity",
            "planned",
            "implemented",
            _accepted(root),
            "github:review-123",
            REVISION,
            "github-review",
        )

    model = CHECK.validate_ledger(
        data, root, receipt_verifier=verifier, repository_revision=REVISION
    )
    assert model.receipts[0].authenticated is True
    assert len(seen) == 1


def test_manual_assertion_is_recordable_but_non_promoting(tmp_path: Path) -> None:
    data, root = _fixture(tmp_path)
    data["receipts"] = [
        _receipt(
            root,
            rid="manual-note",
            kind="advisory",
            source="planned",
            target="planned",
            authentication="manual",
        )
    ]
    assert CHECK.validate_ledger(data, root).receipts[0].authenticated is False
    promoted = copy.deepcopy(data)
    promoted["claims"][0]["maturity"] = "implemented"
    promoted["receipts"] = [
        _receipt(
            root,
            rid="manual-promotion",
            kind="maturity",
            source="planned",
            target="implemented",
            authentication="manual",
        )
    ]
    with pytest.raises(CHECK.ClaimValidationError, match="manual assertions"):
        CHECK.validate_ledger(promoted, root, repository_revision=REVISION)


def test_changed_bytes_wrong_revision_and_wrong_section_replay_are_rejected(
    tmp_path: Path,
) -> None:
    data, root = _fixture(tmp_path)
    data["receipts"] = [
        _receipt(
            root,
            rid="advisory-note",
            kind="advisory",
            source="planned",
            target="planned",
            authentication="manual",
        )
    ]
    changed = copy.deepcopy(data)
    changed["receipts"][0]["accepted_sha256"] = "0" * 64
    with pytest.raises(CHECK.ClaimValidationError, match="accepted bytes"):
        CHECK.validate_ledger(changed, root)
    wrong = copy.deepcopy(data)
    wrong["receipts"][0]["locator"] = "typst:surface.typ#claim-falsifier:pc-test"
    wrong["receipts"][0]["accepted_sha256"] = _accepted(
        root, wrong["receipts"][0]["locator"]
    )
    with pytest.raises(
        CHECK.ClaimValidationError, match="outside its claim owner section"
    ):
        CHECK.validate_ledger(wrong, root)

    promoted = copy.deepcopy(data)
    promoted["claims"][0]["maturity"] = "implemented"
    promoted["receipts"] = [
        _receipt(
            root,
            rid="wrong-revision",
            kind="maturity",
            source="planned",
            target="implemented",
        )
    ]
    with pytest.raises(CHECK.ClaimValidationError, match="current repository revision"):
        CHECK.validate_ledger(
            promoted,
            root,
            receipt_verifier=lambda _attestation: True,
            repository_revision="2" * 40,
        )


def test_transition_matrix_is_exhaustive() -> None:
    states = sorted(CHECK.MATURITY | CHECK.REVIEW_STATES | CHECK.RELEASE_STATES)
    for kind in ("maturity", "review", "release"):
        expected = CHECK.LEGAL_TRANSITIONS[kind]
        for source, target in product(states, repeat=2):
            assert CHECK.legal_transition(kind, source, target) is (
                (source, target) in expected
            )
    for source, target in product(states, repeat=2):
        assert CHECK.legal_transition("advisory", source, target) is (source == target)
    assert CHECK.legal_transition("unknown", "planned", "implemented") is False
