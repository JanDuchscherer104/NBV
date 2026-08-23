"""Validate the G002 principal-claim registry and its surface contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "docs/typst/thesis/data/principal-claims.toml"
SCHEMA = "aria-nbv-principal-claims-v1"
CLAIM_KEYS = frozenset(
    {
        "id",
        "class",
        "rqs",
        "scope",
        "maturity",
        "review_state",
        "release_state",
        "owner",
        "falsifier",
        "limitations",
        "artifact",
        "evidence",
    }
)
EVIDENCE_KEYS = frozenset({"class", "owner", "bibliography"})
RECEIPT_KEYS = frozenset(
    {
        "id",
        "claim_id",
        "kind",
        "from",
        "to",
        "candidate_sha256",
        "author_id",
        "reviewer_id",
        "reviewer_kind",
        "verdict",
        "reviewed_at",
        "locator",
    }
)
ENUMS = {
    "class": frozenset({"rq", "contribution", "result"}),
    "scope": frozenset({"core", "conditional-bridge", "future-work"}),
    "maturity": frozenset({"planned", "implemented", "pilot", "confirmatory"}),
    "review_state": frozenset({"unreviewed", "changes-requested", "approved"}),
    "release_state": frozenset({"withheld", "admissible"}),
}
EVIDENCE_CLASSES = frozenset({"design", "implementation", "pilot", "confirmatory"})
RECEIPT_KINDS = frozenset({"advisory", "maturity", "review", "release"})
REVIEWER_KINDS = frozenset({"automated", "human"})
RECEIPT_STATES = frozenset(
    {
        "planned",
        "implemented",
        "pilot",
        "confirmatory",
        "unreviewed",
        "changes-requested",
        "approved",
        "withheld",
        "admissible",
    }
)
IDENTITY = re.compile(r"^[a-z][a-z0-9-]*$")
CLAIM_ID = re.compile(r"^pc-(?:rq[1-6]|c1|r0)-[a-z0-9-]+$")
REPO_LOCATOR = re.compile(r"^repo:([^:\n]+(?:/[^:\n]+)*):(\d+)-(\d+)$")
BIB_LOCATOR = re.compile(r"^bib:(docs/references\.bib|docs/references-qh\.bib):@([A-Za-z0-9_.:-]+)$")
ARTIFACT = re.compile(r"^repo:([^@\n]+)@sha256:([0-9a-f]{64})$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CLAIMS_MARKER = re.compile(r"^\s*// claims: ([a-z0-9-]+(?:,\s*[a-z0-9-]+)*)\s*$")
CLAIMS_PREFIX = re.compile(r"^\s*// claims:")
EVIDENCE_MARKER = re.compile(r"^\s*// evidence:\s*$")
EVIDENCE_ITEM = re.compile(r"^\s*// - ([^\s]+)\s*$")
REVIEWED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
MAX_MARKER_GAP = 4  # marker may follow only a nearby evidence paragraph


class ClaimValidationError(ValueError):
    """Raised when a principal-claims input violates the closed contract."""


@dataclass(frozen=True)
class Locator:
    raw: str
    kind: str
    identity: str
    path: str
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class Evidence:
    evidence_class: str
    owner: Locator
    bibliography: Locator | None


@dataclass(frozen=True)
class Claim:
    id: str
    claim_class: str
    rqs: tuple[str, ...]
    scope: str
    maturity: str
    review_state: str
    release_state: str
    owner: Locator
    falsifier: Locator
    limitations: tuple[Locator, ...]
    artifact: Locator | None
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class Receipt:
    id: str
    claim_id: str
    kind: str
    from_state: str
    to_state: str
    candidate_sha256: str
    author_id: str
    reviewer_id: str
    reviewer_kind: str
    verdict: str
    reviewed_at: datetime
    locator: Locator


@dataclass(frozen=True)
class Occurrence:
    surface: str
    line: int
    claim_ids: tuple[str, ...]
    evidence: tuple[Locator, ...]


@dataclass(frozen=True)
class SurfaceContract:
    path: str
    claim_ids: tuple[str, ...]
    occurrence_count: int | None


@dataclass(frozen=True)
class PrincipalClaims:
    claims: tuple[Claim, ...]
    receipts: tuple[Receipt, ...]
    occurrences: tuple[Occurrence, ...]
    surfaces: tuple[SurfaceContract, ...]
    locators: tuple[Locator, ...]
    candidate_digest: str


def _fail(message: str) -> NoReturn:
    raise ClaimValidationError(message)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str):
        _fail(f"{field} must be a string")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"{field} must be a string list")
    return tuple(value)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail(f"{field} must be a table")
    return value


def _check_identity(value: object, field: str) -> str:
    result = _string(value, field)
    if not IDENTITY.fullmatch(result):
        _fail(f"{field} must be a grammar-constrained identity")
    return result


def _safe_path(relative: str, root: Path, field: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        _fail(f"{field} has unsafe repository path")
    try:
        target = (root / path).resolve(strict=True)
        target.relative_to(root.resolve())
    except (FileNotFoundError, ValueError):
        _fail(f"{field} points outside or to a missing repository file")
    return target


def _locator(value: object, root: Path, field: str, *, allow_bib: bool = True) -> Locator:
    raw = _string(value, field)
    match = REPO_LOCATOR.fullmatch(raw)
    if match:
        relative, start, end = match.groups()
        target = _safe_path(relative, root, field)
        lines = target.read_text(encoding="utf-8").splitlines()
        first, last = int(start), int(end)
        if first < 1 or first > last or last > len(lines):
            _fail(f"{field} has an unresolved line range")
        return Locator(raw, "repo", relative, relative, first, last)
    if allow_bib:
        match = BIB_LOCATOR.fullmatch(raw)
        if match:
            relative, key = match.groups()
            target = _safe_path(relative, root, field)
            keys = set(
                re.findall(
                    r"^\s*@\w+\{([^,]+),",
                    target.read_text(encoding="utf-8"),
                    re.MULTILINE,
                )
            )
            if key not in keys:
                _fail(f"{field} has a missing BibTeX key")
            return Locator(raw, "bib", key, relative)
    _fail(f"{field} has malformed locator")


def _artifact(value: object, root: Path, field: str) -> Locator:
    raw = _string(value, field)
    match = ARTIFACT.fullmatch(raw)
    if match is None:
        _fail(f"{field} has malformed artifact locator")
    relative, digest = match.groups()
    target = _safe_path(relative, root, field)
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        _fail(f"{field} has a stale artifact digest")
    return Locator(raw, "artifact", digest, relative)


def _evidence(value: object, root: Path, field: str) -> Evidence:
    record = _mapping(value, field)
    if set(record) - EVIDENCE_KEYS or EVIDENCE_KEYS - set(record) - {"bibliography"}:
        _fail(f"{field} has an invalid evidence shape")
    evidence_class = _string(record.get("class"), f"{field}.class")
    if evidence_class not in EVIDENCE_CLASSES:
        _fail(f"{field}.class has an illegal enum")
    bibliography = None
    if "bibliography" in record:
        bibliography = _locator(record["bibliography"], root, f"{field}.bibliography")
        if bibliography.kind != "bib":
            _fail(f"{field}.bibliography must be a bibliography locator")
    return Evidence(
        evidence_class,
        _locator(record.get("owner"), root, f"{field}.owner", allow_bib=False),
        bibliography,
    )


def _claim(record: Mapping[str, object], root: Path, index: int) -> Claim:
    if set(record) - CLAIM_KEYS or CLAIM_KEYS - set(record) - {"artifact"}:
        _fail(f"claim {index} has an invalid key set")
    claim_id = _string(record.get("id"), f"claim {index}.id")
    if not CLAIM_ID.fullmatch(claim_id):
        _fail(f"claim {index} has a malformed id")
    values = {field: _string(record.get(field), f"{claim_id}.{field}") for field in ENUMS}
    for field, value in values.items():
        if value not in ENUMS[field]:
            _fail(f"{claim_id}.{field} has an illegal enum")
    rqs = _strings(record.get("rqs"), f"{claim_id}.rqs")
    if len(set(rqs)) != len(rqs) or any(value not in {f"rq{i}" for i in range(1, 7)} for value in rqs):
        _fail(f"{claim_id}.rqs has an illegal or duplicate identity")
    limitations = tuple(
        _locator(item, root, f"{claim_id}.limitations", allow_bib=False)
        for item in _strings(record.get("limitations"), f"{claim_id}.limitations")
    )
    if not limitations:
        _fail(f"{claim_id}.limitations must be nonempty")
    evidence = (
        tuple(_evidence(item, root, f"{claim_id}.evidence") for item in record["evidence"] if True)
        if isinstance(record["evidence"], list)
        else _fail(f"{claim_id}.evidence must be a table list")
    )
    maturity = values["maturity"]
    if maturity == "planned" and "artifact" in record:
        _fail(f"{claim_id} planned claims cannot have artifacts")
    if maturity != "planned" and "artifact" not in record:
        _fail(f"{claim_id} non-planned claims require an immutable artifact")
    artifact = _artifact(record["artifact"], root, f"{claim_id}.artifact") if "artifact" in record else None
    if values["release_state"] == "admissible":
        if (
            maturity != "confirmatory"
            or values["review_state"] != "approved"
            or not any(item.evidence_class == "confirmatory" for item in evidence)
        ):
            _fail(f"{claim_id} admissibility requires confirmatory evidence and approval")
    claim = Claim(
        claim_id,
        values["class"],
        rqs,
        values["scope"],
        maturity,
        values["review_state"],
        values["release_state"],
        _locator(record.get("owner"), root, f"{claim_id}.owner", allow_bib=False),
        _locator(record.get("falsifier"), root, f"{claim_id}.falsifier", allow_bib=False),
        limitations,
        artifact,
        evidence,
    )
    if maturity == "confirmatory" and not any(item.evidence_class == "confirmatory" for item in evidence):
        _fail(f"{claim_id} confirmatory maturity requires confirmatory evidence")
    return claim


def _receipt(record: Mapping[str, object], root: Path, index: int, known_ids: frozenset[str]) -> Receipt:
    if set(record) != RECEIPT_KEYS:
        _fail(f"receipt {index} must use the exact allowlist")
    rid = _check_identity(record.get("id"), f"receipt {index}.id")
    claim_id = _string(record.get("claim_id"), f"{rid}.claim_id")
    if claim_id not in known_ids:
        _fail(f"{rid} references an unknown claim")
    kind = _string(record.get("kind"), f"{rid}.kind")
    from_state, to_state = (
        _string(record.get("from"), f"{rid}.from"),
        _string(record.get("to"), f"{rid}.to"),
    )
    if kind not in RECEIPT_KINDS or from_state not in RECEIPT_STATES or to_state not in RECEIPT_STATES:
        _fail(f"{rid} has an illegal receipt enum")
    digest = _string(record.get("candidate_sha256"), f"{rid}.candidate_sha256")
    if not SHA256.fullmatch(digest):
        _fail(f"{rid} has a malformed candidate hash")
    author, reviewer = (
        _check_identity(record.get("author_id"), f"{rid}.author_id"),
        _check_identity(record.get("reviewer_id"), f"{rid}.reviewer_id"),
    )
    if author == reviewer:
        _fail(f"{rid} author and reviewer must differ")
    reviewer_kind, verdict = (
        _string(record.get("reviewer_kind"), f"{rid}.reviewer_kind"),
        _string(record.get("verdict"), f"{rid}.verdict"),
    )
    if reviewer_kind not in REVIEWER_KINDS or verdict not in {
        "advisory",
        "implemented",
        "pilot",
        "confirmatory",
        "changes-requested",
        "approved",
        "admissible",
    }:
        _fail(f"{rid} has an illegal reviewer or verdict")
    if reviewer_kind == "automated":
        if from_state != to_state or kind != "advisory" or verdict != "advisory":
            _fail(f"{rid} automated receipts are same-state advisory only")
    elif kind == "advisory" or verdict != to_state:
        _fail(f"{rid} human receipt has an invalid kind or verdict")
    if kind == "advisory" and from_state != to_state:
        _fail(f"{rid} advisory receipts must be same-state")
    if kind == "maturity" and (
        reviewer_kind != "human"
        or (from_state, to_state)
        not in {("planned", "implemented"), ("implemented", "pilot"), ("implemented", "confirmatory")}
    ):
        _fail(f"{rid} has an invalid maturity transition")
    if kind == "review" and (
        reviewer_kind != "human"
        or (from_state, to_state)
        not in {
            ("unreviewed", "changes-requested"),
            ("unreviewed", "approved"),
            ("changes-requested", "approved"),
        }
    ):
        _fail(f"{rid} has an invalid review transition")
    if kind == "release" and (reviewer_kind != "human" or (from_state, to_state) != ("withheld", "admissible")):
        _fail(f"{rid} has an invalid release transition")
    reviewed_at_text = _string(record.get("reviewed_at"), f"{rid}.reviewed_at")
    if not REVIEWED_AT.fullmatch(reviewed_at_text):
        _fail(f"{rid}.reviewed_at has malformed timestamp")
    try:
        reviewed_at = datetime.strptime(reviewed_at_text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(f"{rid}.reviewed_at has an invalid timestamp")
    return Receipt(
        rid,
        claim_id,
        kind,
        from_state,
        to_state,
        digest,
        author,
        reviewer,
        reviewer_kind,
        verdict,
        reviewed_at,
        _locator(record.get("locator"), root, f"{rid}.locator"),
    )


def _candidate_digest(data: Mapping[str, object], root: Path, occurrences: tuple[Occurrence, ...] | None = None) -> str:
    claims = data.get("claims")
    surfaces = data.get("surfaces")
    payload = json.dumps(
        {"claims": claims, "surfaces": surfaces},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    digest = hashlib.sha256()
    evidence_paths: set[str] = set()
    surfaces_for_digest: tuple[SurfaceContract, ...] | None = None
    if isinstance(claims, list):
        for record in claims:
            if isinstance(record, dict):
                values = [record.get("owner"), record.get("falsifier"), *record.get("limitations", [])]
                values.extend(item.get("owner") for item in record.get("evidence", []) if isinstance(item, dict))
                values.extend(item.get("bibliography") for item in record.get("evidence", []) if isinstance(item, dict))
                for value in values:
                    if isinstance(value, str):
                        match = REPO_LOCATOR.fullmatch(value) or BIB_LOCATOR.fullmatch(value)
                        if match:
                            evidence_paths.add(match.group(1))
    if occurrences is None or surfaces_for_digest is None:
        raw_claims = data.get("claims")
        if not isinstance(raw_claims, list):
            _fail("candidate digest requires registry claims")
        claims_for_digest = tuple(_claim(_mapping(item, "claim"), root, index) for index, item in enumerate(raw_claims))
        surfaces_for_digest = _surface_contracts(
            data.get("surfaces"), frozenset(item.id for item in claims_for_digest), root
        )
        if occurrences is None:
            occurrences = validate_active_surfaces(root, claims_for_digest, surfaces_for_digest)
    assert surfaces_for_digest is not None
    assert occurrences is not None
    evidence_paths.update(locator.path for occurrence in occurrences for locator in occurrence.evidence)
    for surface in surfaces_for_digest:
        digest.update(surface.path.encode())
        digest.update(b"\0")
        digest.update(_safe_path(surface.path, root, "active surface").read_bytes())
        digest.update(b"\0")
    for relative in sorted(evidence_paths):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(_safe_path(relative, root, "evidence owner").read_bytes())
        digest.update(b"\0")
    digest.update(b"claims\0")
    digest.update(payload)
    return digest.hexdigest()


def _parse_surface(path: Path, root: Path, known: frozenset[str]) -> tuple[Occurrence, ...]:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    lines = path.read_text(encoding="utf-8").splitlines()
    found = []
    consumed_evidence: set[int] = set()
    for number, line in enumerate(lines):
        marker = CLAIMS_MARKER.fullmatch(line)
        if marker is None:
            if CLAIMS_PREFIX.match(line):
                _fail(f"orphan or malformed evidence in {relative}:{number + 1}")
            continue
        ids = tuple(item.strip() for item in marker.group(1).split(","))
        if len(set(ids)) != len(ids) or any(item not in known for item in ids):
            _fail(f"unknown or duplicate claim marker in {relative}:{number + 1}")
        if number < 2 or not EVIDENCE_MARKER.fullmatch(lines[number - 1]):
            _fail(f"claim marker in {relative}:{number + 1} lacks preceding evidence")
        consumed_evidence.add(number - 1)
        evidence: list[Locator] = []
        cursor = number - 2
        while cursor >= 0:
            item = EVIDENCE_ITEM.fullmatch(lines[cursor])
            if item is None:
                break
            consumed_evidence.add(cursor)
            locator = _locator(item.group(1), root, f"{relative}:{number + 1}.evidence")
            if locator.kind == "repo" and (
                locator.path != relative
                or locator.end is None
                or locator.end >= number + 1
                or number + 1 - locator.end > MAX_MARKER_GAP
            ):
                _fail(f"{relative}:{number + 1} evidence is not adjacent local evidence")
            evidence.append(locator)
            cursor -= 1
        if not evidence:
            _fail(f"claim marker in {relative}:{number + 1} has malformed evidence")
        if not any(locator.kind == "repo" for locator in evidence):
            _fail(f"claim marker in {relative}:{number + 1} lacks same-surface repository evidence")
        found.append(Occurrence(relative, number + 1, ids, tuple(reversed(evidence))))
    for number, line in enumerate(lines):
        if (EVIDENCE_MARKER.fullmatch(line) or EVIDENCE_ITEM.fullmatch(line)) and number not in consumed_evidence:
            _fail(f"orphan or malformed evidence in {relative}:{number + 1}")
    return tuple(found)


def _surface_contracts(value: object, known_ids: frozenset[str], root: Path) -> tuple[SurfaceContract, ...]:
    if not isinstance(value, list) or not value:
        _fail("surfaces must be a nonempty array of tables")
    contracts: list[SurfaceContract] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        record = _mapping(item, f"surface {index}")
        if set(record) - {"path", "claim_ids", "occurrence_count"}:
            _fail(f"surface {index} has an invalid key set")
        path = _string(record.get("path"), f"surface {index}.path")
        if path in seen:
            _fail(f"duplicate surface contract {path}")
        seen.add(path)
        claim_ids = _strings(record.get("claim_ids"), f"{path}.claim_ids")
        if not claim_ids or len(set(claim_ids)) != len(claim_ids):
            _fail(f"{path}.claim_ids must be nonempty and unique")
        if any(not CLAIM_ID.fullmatch(item) or item not in known_ids for item in claim_ids):
            _fail(f"{path}.claim_ids contains an unknown claim")
        count = record.get("occurrence_count")
        if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 1):
            _fail(f"{path}.occurrence_count must be a positive integer")
        _safe_path(path, root, f"surface {index}.path")
        contracts.append(SurfaceContract(path, claim_ids, count))
    if set().union(*(set(item.claim_ids) for item in contracts)) != known_ids:
        _fail("surface contracts must route every registry claim exactly")
    return tuple(contracts)


def validate_active_surfaces(
    root: Path = ROOT,
    claims: tuple[Claim, ...] | None = None,
    surfaces: tuple[SurfaceContract, ...] | None = None,
) -> tuple[Occurrence, ...]:
    if claims is None or surfaces is None:
        _fail("active surface validation requires registry claims and surface contracts")
    known = frozenset(item.id for item in claims)
    occurrences: list[Occurrence] = []
    for contract in surfaces:
        relative = contract.path
        path = _safe_path(relative, root, f"active surface {relative}")
        parsed = _parse_surface(path, root, known)
        if not parsed:
            _fail(f"{relative} violates its registry surface contract")
        if contract.occurrence_count is not None and len(parsed) != contract.occurrence_count:
            _fail(f"{relative} has the wrong occurrence count")
        if contract.occurrence_count is not None and any(
            set(item.claim_ids) != set(contract.claim_ids) for item in parsed
        ):
            _fail(f"{relative} has a non-parity occurrence")
        if set().union(*(set(item.claim_ids) for item in parsed)) != set(contract.claim_ids):
            _fail(f"{relative} has the wrong claim membership")
        occurrences.extend(parsed)
    return tuple(occurrences)


def validate_ledger(data: Mapping[str, object], root: Path = ROOT) -> PrincipalClaims:
    """Public projection-ready validator; TOML parsing remains registry-internal."""
    if set(data) != {"schema", "claims", "surfaces", "receipts"} or data.get("schema") != SCHEMA:
        _fail("ledger must contain exactly schema, claims, surfaces, and receipts")
    raw_claims, raw_surfaces, raw_receipts = data.get("claims"), data.get("surfaces"), data.get("receipts")
    if not isinstance(raw_claims, list) or not raw_claims or not isinstance(raw_receipts, list):
        _fail("claims and receipts must be arrays of tables")
    claims = tuple(_claim(_mapping(item, "claim"), root, index) for index, item in enumerate(raw_claims))
    known_ids = frozenset(item.id for item in claims)
    if len(known_ids) != len(claims):
        _fail("ledger claim IDs must be unique")
    surfaces = _surface_contracts(raw_surfaces, known_ids, root)
    receipts = tuple(
        _receipt(_mapping(item, "receipt"), root, index, known_ids) for index, item in enumerate(raw_receipts)
    )
    occurrences = validate_active_surfaces(root, claims, surfaces)
    for claim in claims:
        if not any(
            claim.id in occurrence.claim_ids
            and any(
                locator.kind == "repo" and locator.path == claim.owner.path and locator.raw == claim.owner.raw
                for locator in occurrence.evidence
            )
            for occurrence in occurrences
        ):
            _fail(f"{claim.id} owner is not represented by adjacent same-claim surface evidence")
    digest = _candidate_digest(data, root, occurrences)
    previous: dict[tuple[str, str], Receipt] = {}
    seen_ids: set[str] = set()
    for receipt in receipts:
        if receipt.id in seen_ids:
            _fail(f"duplicate receipt id {receipt.id}")
        seen_ids.add(receipt.id)
        if receipt.candidate_sha256 != digest:
            _fail(f"{receipt.id} does not review the current candidate digest")
        prior = previous.get((receipt.claim_id, receipt.kind))
        if prior and (receipt.from_state != prior.to_state or receipt.reviewed_at < prior.reviewed_at):
            _fail(f"{receipt.id} is not a monotonic receipt sequence")
        initial = {"maturity": "planned", "review": "unreviewed", "release": "withheld"}.get(receipt.kind)
        if prior is None and receipt.from_state != initial and receipt.kind != "advisory":
            _fail(f"{receipt.id} does not start at the dimension's initial state")
        previous[(receipt.claim_id, receipt.kind)] = receipt
    for claim in claims:
        required = (
            ("maturity", claim.maturity != "planned"),
            ("review", claim.review_state != "unreviewed"),
            ("release", claim.release_state == "admissible"),
        )
        current_states = {"maturity": claim.maturity, "review": claim.review_state, "release": claim.release_state}
        for kind, needed in required:
            latest = previous.get((claim.id, kind))
            if latest is not None and latest.to_state != current_states[kind]:
                _fail(f"{latest.id} final receipt state does not match the claim")
            if needed and not any(
                r.claim_id == claim.id
                and r.kind == kind
                and r.to_state == current_states[kind]
                and r.reviewer_kind == "human"
                and r.candidate_sha256 == digest
                for r in receipts
            ):
                _fail(f"{claim.id} requires a current human {kind} receipt")
    all_locators: list[Locator] = []
    for claim in claims:
        all_locators.extend((claim.owner, claim.falsifier, *claim.limitations))
        for evidence in claim.evidence:
            all_locators.append(evidence.owner)
            if evidence.bibliography is not None:
                all_locators.append(evidence.bibliography)
        if claim.artifact is not None:
            all_locators.append(claim.artifact)
    all_locators.extend(receipt.locator for receipt in receipts)
    all_locators.extend(locator for occurrence in occurrences for locator in occurrence.evidence)
    locators = tuple({item.raw: item for item in all_locators}.values())
    return PrincipalClaims(claims, receipts, occurrences, surfaces, locators, digest)


def read_principal_claims(path: Path = DEFAULT_LEDGER, root: Path = ROOT) -> PrincipalClaims:
    """Read the registry and return its validated projection-ready model."""
    return validate_ledger(tomllib.loads(path.read_text(encoding="utf-8")), root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    model = read_principal_claims(args.ledger, ROOT)
    print(f"validated {len(model.claims)} principal claims and {len(model.receipts)} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
