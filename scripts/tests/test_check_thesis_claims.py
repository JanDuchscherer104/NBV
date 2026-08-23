"""Negative-first tests for the G002 principal-claim contract."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_thesis_claims", ROOT / "scripts/check_thesis_claims.py")
assert SPEC and SPEC.loader
CHECK = importlib.util.module_from_spec(SPEC)
sys.modules["check_thesis_claims"] = CHECK
SPEC.loader.exec_module(CHECK)


def ledger() -> dict[str, Any]:
    import tomllib

    return tomllib.loads((ROOT / "docs/typst/thesis/data/principal-claims.toml").read_text())


def surface_paths(data: dict[str, Any]) -> tuple[str, ...]:
    return tuple(item["path"] for item in data["surfaces"])


def fixture(tmp_path: Path) -> Path:
    data = ledger()
    contracts = {item["path"]: item for item in data["surfaces"]}
    for relative in surface_paths(data):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        allowed = tuple(contracts[relative]["claim_ids"])
        required = contracts[relative].get("occurrence_count", 1)
        lines = ["content"] * 219
        if relative.endswith("01-research-questions.typ"):
            grouped: dict[int, list[str]] = {}
            ranges: dict[int, str] = {}
            for claim in data["claims"]:
                locator = claim["owner"]
                start, end = map(int, locator.rsplit(":", 1)[1].split("-"))
                grouped.setdefault(end, []).append(claim["id"])
                ranges[end] = locator
            for end, claim_ids in grouped.items():
                lines[end] = f"// - {ranges[end]}"
                lines[end + 1] = "// evidence:"
                lines[end + 2] = f"// claims: {', '.join(claim_ids)}"
        else:
            blocks = []
            for index in range(required):
                evidence_line = 220 + index * 4
                blocks.append(
                    f"// - repo:{relative}:{evidence_line}-{evidence_line}\n// evidence:\n// claims: {', '.join(allowed)}\n"
                )
            path.write_text("\n".join(lines) + "\n" + "\n".join(blocks))
            continue
        path.write_text("\n".join(lines) + "\n")
    return tmp_path


def candidate(data: dict[str, Any], root: Path) -> str:
    return cast(str, CHECK._candidate_digest(data, root))


def receipt(root: Path, data: dict[str, Any], **overrides: str) -> dict[str, str]:
    value = {
        "id": "receipt-one",
        "claim_id": "pc-rq1-endpoint-contract",
        "kind": "advisory",
        "from": "planned",
        "to": "planned",
        "candidate_sha256": candidate(data, root),
        "author_id": "author-one",
        "reviewer_id": "reviewer-one",
        "reviewer_kind": "automated",
        "verdict": "advisory",
        "reviewed_at": "2026-08-23T12:00:00Z",
        "locator": "repo:docs/typst/thesis/sections/01-research-questions.typ:1-1",
    }
    value.update(overrides)
    return value


def test_approved_shape_and_projection_api(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    model = CHECK.validate_ledger(ledger(), root)
    assert len(model.claims) == 8 and not model.receipts
    assert model.candidate_digest == candidate(ledger(), root)
    assert all(
        claim.maturity == "planned" and claim.review_state == "unreviewed" and claim.release_state == "withheld"
        for claim in model.claims
    )
    assert all(claim.limitations and all(item.kind == "repo" for item in claim.limitations) for claim in model.claims)
    assert all(isinstance(item, CHECK.Evidence) for claim in model.claims for item in claim.evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("class", "bridge"),
        ("scope", "online-discrete-bridge"),
        ("maturity", "reviewed"),
        ("review_state", "reviewed"),
        ("release_state", "released"),
    ],
)
def test_closed_enums(tmp_path: Path, field: str, value: str) -> None:
    root = fixture(tmp_path)
    data = ledger()
    data["claims"][0][field] = value
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(data, root)


def test_claim_class_scope_assignments() -> None:
    data = ledger()
    claims = {item["id"]: item for item in data["claims"]}
    assert all(
        claims[
            f"pc-rq{i}-"
            + {
                1: "endpoint-contract",
                2: "lookahead-headroom",
                3: "actor-oracle-separation",
                4: "candidate-rollout-support",
            }[i]
        ]["class"]
        == "rq"
        for i in range(1, 5)
    )
    assert (
        claims["pc-rq5-online-discrete-bridge"]["class"] == "rq"
        and claims["pc-rq5-online-discrete-bridge"]["scope"] == "conditional-bridge"
    )
    assert (
        claims["pc-rq6-continuous-simulator-bridge"]["class"] == "rq"
        and claims["pc-rq6-continuous-simulator-bridge"]["scope"] == "conditional-bridge"
    )
    assert claims["pc-c1-auditable-experiment-contract"]["class"] == "contribution"
    assert claims["pc-r0-no-confirmatory-policy-result"]["class"] == "result"


@pytest.mark.parametrize(
    "claim_id,wrong_range",
    [
        ("pc-rq5-online-discrete-bridge", "198-205"),
        ("pc-rq6-continuous-simulator-bridge", "183-190"),
        ("pc-r0-no-confirmatory-policy-result", "183-190"),
    ],
)
def test_claim_owner_must_be_adjacent_same_claim_surface_evidence(
    tmp_path: Path, claim_id: str, wrong_range: str
) -> None:
    root = fixture(tmp_path)
    data = ledger()
    claim = next(item for item in data["claims"] if item["id"] == claim_id)
    locator = f"repo:docs/typst/thesis/sections/01-research-questions.typ:{wrong_range}"
    claim.update(owner=locator, falsifier=locator, limitations=[locator])
    claim["evidence"][0]["owner"] = locator
    with pytest.raises(CHECK.ClaimValidationError, match="adjacent same-claim"):
        CHECK.validate_ledger(data, root)


def test_limitations_and_evidence_reject_semantic_shapes(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    mutations: tuple[Callable[[dict[str, Any]], None], ...] = (
        lambda d: d["claims"][0].update(limitations=["pending"]),
        lambda d: d["claims"][0]["evidence"][0].update(identity="semantic"),
        lambda d: d["claims"][0]["evidence"][0].update(**{"class": "unknown"}),
    )
    for mutation in mutations:
        data = ledger()
        mutation(data)
        with pytest.raises(CHECK.ClaimValidationError):
            CHECK.validate_ledger(data, root)


def test_artifact_matrix_and_admissibility(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    data = ledger()
    artifact = root / "artifact.bin"
    artifact.write_bytes(b"immutable")
    data["claims"][0]["maturity"] = "implemented"
    data["claims"][0]["artifact"] = f"repo:artifact.bin@sha256:{hashlib.sha256(b'immutable').hexdigest()}"
    data["receipts"] = [
        receipt(
            root,
            data,
            kind="maturity",
            **{"from": "planned"},
            to="implemented",
            reviewer_kind="human",
            verdict="implemented",
        )
    ]
    CHECK.validate_ledger(data, root)
    planned = ledger()
    planned["claims"][0]["artifact"] = data["claims"][0]["artifact"]
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(planned, root)
    admissible = copy.deepcopy(data)
    admissible["claims"][0].update(maturity="confirmatory", review_state="approved", release_state="admissible")
    admissible["claims"][0]["evidence"].append(
        {
            "class": "confirmatory",
            "owner": "repo:docs/typst/thesis/sections/01-research-questions.typ:1-1",
        }
    )
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(admissible, root)


@pytest.mark.parametrize(
    "overrides",
    [
        {"from": "planned", "to": "pilot", "reviewer_kind": "automated"},
        {
            "from": "planned",
            "to": "confirmatory",
            "reviewer_kind": "human",
            "kind": "review",
            "verdict": "confirmatory",
        },
        {
            "from": "pilot",
            "to": "confirmatory",
            "reviewer_kind": "human",
            "kind": "review",
            "verdict": "confirmatory",
        },
        {
            "from": "confirmatory",
            "to": "approved",
            "reviewer_kind": "automated",
            "verdict": "approved",
        },
        {
            "from": "planned",
            "to": "approved",
            "reviewer_kind": "human",
            "kind": "review",
            "verdict": "approved",
        },
    ],
)
def test_forbidden_receipt_promotions(tmp_path: Path, overrides: dict[str, str]) -> None:
    root = fixture(tmp_path)
    data = ledger()
    data["receipts"] = [receipt(root, data, **overrides)]
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(data, root)


def test_same_state_automated_advisory_is_allowed(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    data = ledger()
    data["receipts"] = [receipt(root, data)]
    model = CHECK.validate_ledger(data, root)
    assert model.receipts[0].reviewer_kind == "automated"


def test_changes_requested_requires_current_human_review_receipt(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    data = ledger()
    data["claims"][0]["review_state"] = "changes-requested"
    with pytest.raises(CHECK.ClaimValidationError, match="current human review"):
        CHECK.validate_ledger(data, root)

    data["receipts"] = [
        receipt(
            root,
            data,
            kind="review",
            **{"from": "unreviewed"},
            to="changes-requested",
            reviewer_kind="human",
            verdict="changes-requested",
        )
    ]
    CHECK.validate_ledger(data, root)


def test_surface_contracts_use_registry_paths_and_reject_unsafe_paths(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    data = ledger()
    claims = tuple(CHECK._claim(item, root, index) for index, item in enumerate(data["claims"]))
    contracts = []
    for index, item in enumerate(data["surfaces"]):
        relative = f"registry-surface-{index}.typ"
        path = root / relative
        blocks = []
        for occurrence in range(item.get("occurrence_count", 1)):
            line = occurrence * 4 + 1
            blocks.append(
                f"// - repo:{relative}:{line}-{line}\n// evidence:\n// claims: {', '.join(item['claim_ids'])}\n"
            )
        path.write_text("".join(blocks))
        replacement = dict(item)
        replacement["path"] = relative
        contracts.append(replacement)
    parsed = CHECK._surface_contracts(contracts, frozenset(item.id for item in claims), root)
    assert tuple(item.path for item in parsed) == tuple(
        f"registry-surface-{index}.typ" for index in range(len(contracts))
    )
    assert CHECK.validate_active_surfaces(root, claims, parsed)

    unsafe = list(contracts)
    unsafe[0] = {**unsafe[0], "path": "../escape.typ"}
    with pytest.raises(CHECK.ClaimValidationError, match="unsafe repository path"):
        CHECK._surface_contracts(unsafe, frozenset(item.id for item in claims), root)


def test_candidate_digest_invalidates_receipt_on_claim_or_surface_change(
    tmp_path: Path,
) -> None:
    root = fixture(tmp_path)
    data = ledger()
    data["receipts"] = [receipt(root, data)]
    CHECK.validate_ledger(data, root)
    changed = copy.deepcopy(data)
    changed["claims"][0]["scope"] = "future-work"
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(changed, root)
    relative = surface_paths(data)[0]
    (root / relative).write_text((root / relative).read_text() + "\n")
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(data, root)


def test_candidate_digest_includes_referenced_evidence_owner_bytes(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    data = ledger()
    before = candidate(data, root)
    evidence_owner = root / "docs/typst/thesis/sections/01-research-questions.typ"
    evidence_owner.write_text(evidence_owner.read_text() + "\nchanged evidence owner\n")
    assert candidate(data, root) != before


def test_literature_marker_requires_same_surface_repo_and_valid_bibliography(tmp_path: Path) -> None:
    surface = tmp_path / "surface.typ"
    bibliography = tmp_path / "docs/references.bib"
    bibliography.parent.mkdir()
    bibliography.write_text("@article{Example-key,\n  title = {Example}\n}\n")
    surface.write_text(
        "A claim-bearing paragraph.\n"
        "// - repo:surface.typ:1-1\n"
        "// - bib:docs/references.bib:@Example-key\n"
        "// evidence:\n"
        "// claims: pc-rq1-endpoint-contract\n"
    )
    occurrences = CHECK._parse_surface(surface, tmp_path, frozenset({"pc-rq1-endpoint-contract"}))
    assert [item.kind for item in occurrences[0].evidence] == ["repo", "bib"]

    surface.write_text("// - bib:docs/references.bib:@Example-key\n// evidence:\n// claims: pc-rq1-endpoint-contract\n")
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK._parse_surface(surface, tmp_path, frozenset({"pc-rq1-endpoint-contract"}))


def test_matrix_rejects_unknown_or_wrong_surface_ids(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    path = root / surface_paths(ledger())[3]
    path.write_text(path.read_text().replace("pc-r0-no-confirmatory-policy-result", "pc-rq1-endpoint-contract"))
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(ledger(), root)


def test_matrix_accepts_partitioned_multi_marker_surfaces(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    relative = surface_paths(ledger())[2]
    path = root / relative
    allowed = tuple(next(item for item in ledger()["surfaces"] if item["path"] == relative)["claim_ids"])
    ids = list(allowed)
    path.write_text(
        "content\n" * 219
        + "\n".join(
            [
                f"// - repo:{relative}:220-220\n// evidence:\n// claims: {', '.join(ids[:4])}\n",
                f"// - repo:{relative}:224-224\n// evidence:\n// claims: {', '.join(ids[4:])}\n",
            ]
        )
    )
    data = ledger()
    data["surfaces"] = list(data["surfaces"])
    occurrences = CHECK.validate_active_surfaces(
        root,
        tuple(CHECK._claim(item, root, index) for index, item in enumerate(data["claims"])),
        CHECK._surface_contracts(data["surfaces"], frozenset(item["id"] for item in data["claims"]), root),
    )
    surface_occurrences = [item for item in occurrences if item.surface == relative]
    assert len(surface_occurrences) == 2
    assert set().union(*(set(item.claim_ids) for item in surface_occurrences)) == set(allowed)


def test_matrix_rejects_missing_union_claim(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    relative = surface_paths(ledger())[3]
    path = root / relative
    path.write_text(
        "content\n" * 219 + f"// - repo:{relative}:220-220\n// evidence:\n"
        "// claims: pc-c1-auditable-experiment-contract\n"
    )
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(ledger(), root)


def test_matrix_rejects_extra_results_claim(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    path = root / surface_paths(ledger())[3]
    path.write_text(
        path.read_text().replace(
            "pc-r0-no-confirmatory-policy-result",
            "pc-r0-no-confirmatory-policy-result, pc-rq1-endpoint-contract",
        )
    )
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(ledger(), root)


def test_main_requires_two_adjacent_parity_occurrences(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    path = root / surface_paths(ledger())[0]
    lines = path.read_text().splitlines()
    claims_lines = [index for index, line in enumerate(lines) if "// claims:" in line]
    lines[claims_lines[-1]] = lines[claims_lines[-1]].replace("pc-rq4-candidate-rollout-support, ", "")
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(ledger(), root)


def test_main_requires_both_abstract_occurrences(tmp_path: Path) -> None:
    root = fixture(tmp_path)
    path = root / surface_paths(ledger())[0]
    text = path.read_text()
    first, _ = text.rsplit("// - repo:", 1)
    path.write_text(first)
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK.validate_ledger(ledger(), root)


@pytest.mark.parametrize(
    "bad",
    [
        "// claims: pc-rq1-endpoint-contract\n// evidence:\n// - repo:surface.typ:220-220\n",
        "// - repo:surface.typ:217-217\n// evidence:\n// claims: pc-rq1-endpoint-contract\n",
    ],
)
def test_marker_tail_or_wrong_range_fails(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "surface.typ"
    path.write_text("content\n" * 219 + bad)
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK._parse_surface(path, tmp_path, frozenset({"pc-rq1-endpoint-contract"}))


@pytest.mark.parametrize(
    "bad",
    [
        "// claims: pc-rq1-endpoint-contract\n// evidence:\n// - repo:docs/typst/thesis/main.typ:1-1\n",
        "// evidence:\n// - repo:docs/typst/thesis/main.typ:1-1\n// claims: pc-rq1-endpoint-contract\n",
        "// claims: pc-rq1-endpoint-contract\n// evidence:\n// - repo:docs/typst/thesis/other.typ:1-1\n",
    ],
)
def test_marker_adjacency_or_orphan_evidence_fails(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "surface.typ"
    path.write_text(bad)
    with pytest.raises(CHECK.ClaimValidationError):
        CHECK._parse_surface(path, tmp_path, frozenset({"pc-rq1-endpoint-contract"}))
