#!/usr/bin/env python3
"""Validate the thesis claim ledger and its anchored prose membership."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Protocol

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "docs/typst/thesis/data/principal-claims.toml"
SCHEMA = "aria-nbv-principal-claims-v2"
CLAIM_CLASSES = frozenset({"rq", "contribution", "result"})
RELEASE_APPLICABILITY = frozenset({"required", "conditional", "non-release"})
MATURITY = frozenset({"planned", "implemented", "pilot", "confirmatory"})
OUTCOMES = frozenset(
    {"missing", "failed", "completed-negative", "conditional", "confirmatory"}
)
RELEASABLE_OUTCOMES = frozenset({"completed-negative", "confirmatory"})
REVIEW_STATES = frozenset({"unreviewed", "changes-requested", "approved"})
RELEASE_STATES = frozenset({"withheld", "admissible"})
AUTHENTICATION = frozenset(
    {
        "manual",
        "github-review",
        "github-thread",
        "signed-artifact",
        "equivalent-principal",
    }
)
RECEIPT_KINDS = frozenset({"maturity", "review", "release", "advisory"})
LEGAL_TRANSITIONS = {
    "maturity": frozenset(
        {
            ("planned", "implemented"),
            ("implemented", "pilot"),
            ("pilot", "confirmatory"),
        }
    ),
    "review": frozenset(
        {
            ("unreviewed", "changes-requested"),
            ("unreviewed", "approved"),
            ("changes-requested", "approved"),
        }
    ),
    "release": frozenset({("withheld", "admissible")}),
}
INITIAL_STATES = {"maturity": "planned", "review": "unreviewed", "release": "withheld"}
IDENTITY = re.compile(r"^[a-z][a-z0-9-]*$")
CLAIM_ID = re.compile(r"^pc-[a-z0-9-]+$")
ANCHOR = re.compile(
    r"^typst:([^#\n]+)#(claim-(owner|falsifier|limitation):([a-z0-9-]+))$"
)
CODE = re.compile(r"^code:([^#\n]+)(?:#([A-Za-z_][A-Za-z0-9_.:-]*))?$")
ARTIFACT = re.compile(r"^artifact:([^@\n]+)@sha256:([0-9a-f]{64})$")
BIB = re.compile(r"^bib:(docs/references(?:-qh)?\.bib)#([A-Za-z0-9_.:-]+)$")
RECEIPT_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REVISION = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
CODE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cu",
        ".cuh",
        ".go",
        ".h",
        ".hpp",
        ".js",
        ".py",
        ".rs",
        ".sh",
        ".ts",
    }
)


class ClaimValidationError(ValueError):
    """Raised when a ledger violates the closed claim contract."""


@dataclass(frozen=True)
class Locator:
    raw: str
    kind: str
    path: str
    identity: str
    role: str


@dataclass(frozen=True)
class Evidence:
    role: str
    locator: Locator


@dataclass(frozen=True)
class Claim:
    id: str
    claim_class: str
    rqs: tuple[str, ...]
    release_applicability: str
    maturity: str
    outcome: str
    review_state: str
    release_state: str
    owner: Locator
    falsifier: Locator
    limitations: tuple[Locator, ...]
    evidence: tuple[Evidence, ...]


@dataclass(frozen=True)
class ReceiptAttestation:
    """Immutable authentication input supplied to an external verifier seam."""

    claim_id: str
    kind: str
    from_state: str
    to_state: str
    canonical_slice_sha256: str
    principal: str
    repository_revision: str
    authentication_kind: str


class ReceiptVerifier(Protocol):
    """Authenticate a receipt attestation without prescribing its backend."""

    def __call__(self, attestation: ReceiptAttestation, /) -> bool: ...


@dataclass(frozen=True)
class Receipt:
    id: str
    claim_id: str
    kind: str
    from_state: str
    to_state: str
    principal: str
    authentication: str
    verdict: str
    locator: Locator
    accepted_sha256: str
    repository_revision: str
    authenticated: bool


@dataclass(frozen=True)
class Occurrence:
    surface: str
    anchor: str
    claim_id: str
    role: str
    start_byte: int
    end_byte: int
    accepted_sha256: str

    @property
    def canonical_span(self) -> tuple[str, int, int]:
        return (self.surface, self.start_byte, self.end_byte)


@dataclass(frozen=True)
class PrincipalClaims:
    claims: tuple[Claim, ...]
    receipts: tuple[Receipt, ...]
    occurrences: tuple[Occurrence, ...]
    candidate_digest: str


def _fail(message: str) -> NoReturn:
    raise ClaimValidationError(message)


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{field} must be a non-empty string")
    return value


def _strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        _fail(f"{field} must be a string list")
    return tuple(value)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail(f"{field} must be a table")
    return value


def _resource(relative: str, root: Path, field: str) -> tuple[Path, str]:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        _fail(f"{field} has an unsafe path")
    try:
        resolved = (root / candidate).resolve(strict=True)
        canonical = resolved.relative_to(root.resolve()).as_posix()
    except (FileNotFoundError, OSError, RuntimeError, ValueError):
        _fail(f"{field} points to a missing or external file")
    if not resolved.is_file():
        _fail(f"{field} must point to a file")
    return resolved, canonical


def _locator(value: object, root: Path, field: str, role: str) -> Locator:
    raw = _string(value, field)
    match = ANCHOR.fullmatch(raw)
    if match:
        path, anchor, anchor_role, _claim_id = match.groups()
        _, canonical = _resource(path, root, field)
        if role in {"owner", "falsifier", "limitation"} and anchor_role != role:
            _fail(f"{field} anchor prefix is incompatible with role {role}")
        return Locator(raw, "typst-anchor", canonical, anchor, role)
    match = CODE.fullmatch(raw)
    if match:
        path, identity = match.groups()
        resolved, canonical = _resource(path, root, field)
        if resolved.suffix.casefold() not in CODE_SUFFIXES or canonical.startswith(
            "docs/typst/"
        ):
            _fail(f"{field} implementation code locator must resolve to a code owner")
        return Locator(raw, "code", canonical, identity or canonical, role)
    match = ARTIFACT.fullmatch(raw)
    if match:
        path, digest = match.groups()
        resolved, canonical = _resource(path, root, field)
        if hashlib.sha256(resolved.read_bytes()).hexdigest() != digest:
            _fail(f"{field} has a stale artifact digest")
        return Locator(raw, "artifact", canonical, digest, role)
    match = BIB.fullmatch(raw)
    if match:
        path, key = match.groups()
        resolved, canonical = _resource(path, root, field)
        if not re.search(
            rf"^\s*@\w+\{{{re.escape(key)},",
            resolved.read_text(encoding="utf-8"),
            re.MULTILINE,
        ):
            _fail(f"{field} references a missing bibliography key")
        return Locator(raw, "bibliography", canonical, key, role)
    _fail(f"{field} has a malformed locator")


def _claim(record: Mapping[str, object], root: Path, index: int) -> Claim:
    allowed = {
        "id",
        "class",
        "rqs",
        "release_applicability",
        "maturity",
        "outcome",
        "review_state",
        "release_state",
        "owner",
        "falsifier",
        "limitations",
        "evidence",
    }
    if set(record) != allowed:
        _fail(f"claim {index} has an invalid key set")
    claim_id = _string(record["id"], f"claim {index}.id")
    if not CLAIM_ID.fullmatch(claim_id):
        _fail(f"{claim_id} has a malformed id")
    values = {
        key: _string(record[key], f"{claim_id}.{key}")
        for key in (
            "class",
            "release_applicability",
            "maturity",
            "outcome",
            "review_state",
            "release_state",
        )
    }
    enums = {
        "class": CLAIM_CLASSES,
        "release_applicability": RELEASE_APPLICABILITY,
        "maturity": MATURITY,
        "outcome": OUTCOMES,
        "review_state": REVIEW_STATES,
        "release_state": RELEASE_STATES,
    }
    for key, value in values.items():
        if value not in enums[key]:
            _fail(f"{claim_id}.{key} has an illegal value")
    rqs = _strings(record["rqs"], f"{claim_id}.rqs")
    if len(set(rqs)) != len(rqs) or any(
        not re.fullmatch(r"rq[1-6]", item) for item in rqs
    ):
        _fail(f"{claim_id}.rqs has an illegal or duplicate identity")
    owner = _locator(record["owner"], root, f"{claim_id}.owner", "owner")
    falsifier = _locator(
        record["falsifier"], root, f"{claim_id}.falsifier", "falsifier"
    )
    limitations = tuple(
        _locator(item, root, f"{claim_id}.limitations", "limitation")
        for item in _strings(record["limitations"], f"{claim_id}.limitations")
    )
    if not limitations:
        _fail(f"{claim_id}.limitations must not be empty")
    if any(
        locator.kind != "typst-anchor" for locator in (owner, falsifier, *limitations)
    ):
        _fail(f"{claim_id} owner, falsifier, and limitation must use Typst anchors")
    evidence_raw = record["evidence"]
    if not isinstance(evidence_raw, list) or not evidence_raw:
        _fail(f"{claim_id}.evidence must be a non-empty table list")
    evidence: list[Evidence] = []
    for item in evidence_raw:
        row = _mapping(item, f"{claim_id}.evidence")
        if set(row) != {"role", "locator"}:
            _fail(f"{claim_id}.evidence has an invalid key set")
        role = _string(row["role"], f"{claim_id}.evidence.role")
        if role not in {"implementation", "empirical"}:
            _fail(f"{claim_id}.evidence.role is incompatible")
        locator = _locator(row["locator"], root, f"{claim_id}.evidence.locator", role)
        if role == "implementation" and locator.kind != "code":
            _fail(f"{claim_id} implementation evidence must use a code locator")
        if role == "empirical" and locator.kind not in {"artifact", "bibliography"}:
            _fail(
                f"{claim_id} empirical evidence must use an artifact or bibliography locator"
            )
        evidence.append(Evidence(role, locator))
    if values["release_state"] == "admissible":
        if (
            values["release_applicability"] != "required"
            or values["outcome"] not in RELEASABLE_OUTCOMES
            or values["maturity"] != "confirmatory"
            or values["review_state"] != "approved"
        ):
            _fail(
                f"{claim_id} admissibility requires required, completed, approved evidence"
            )
        if not any(item.role == "empirical" for item in evidence):
            _fail(f"{claim_id} admissibility requires empirical evidence")
    return Claim(
        claim_id,
        values["class"],
        rqs,
        values["release_applicability"],
        values["maturity"],
        values["outcome"],
        values["review_state"],
        values["release_state"],
        owner,
        falsifier,
        limitations,
        tuple(evidence),
    )


def _active_typst_source(text: str) -> str:
    """Mask inactive Typst text while preserving source offsets and newlines."""
    active = list(text)
    index = 0
    in_string = False
    block_depth = 0
    raw_delimiter = 0
    while index < len(text):
        pair = text[index : index + 2]
        if block_depth:
            if pair == "/*":
                active[index : index + 2] = "  "
                block_depth += 1
                index += 2
            elif pair == "*/":
                active[index : index + 2] = "  "
                block_depth -= 1
                index += 2
            else:
                if text[index] != "\n":
                    active[index] = " "
                index += 1
            continue
        if raw_delimiter:
            if text[index] == "`":
                end = index
                while end < len(text) and text[end] == "`":
                    end += 1
                active[index:end] = " " * (end - index)
                if end - index == raw_delimiter:
                    raw_delimiter = 0
                index = end
            else:
                if text[index] != "\n":
                    active[index] = " "
                index += 1
            continue
        if in_string:
            if text[index] != "\n":
                active[index] = " "
            if text[index] == "\\" and index + 1 < len(text):
                if text[index + 1] != "\n":
                    active[index + 1] = " "
                index += 2
            else:
                if text[index] == '"':
                    in_string = False
                index += 1
            continue
        if text[index] == '"':
            active[index] = " "
            in_string = True
            index += 1
        elif text[index] == "`":
            end = index
            while end < len(text) and text[end] == "`":
                end += 1
            active[index:end] = " " * (end - index)
            raw_delimiter = end - index
            index = end
        elif pair == "//":
            end = text.find("\n", index)
            end = len(text) if end < 0 else end
            active[index:end] = " " * (end - index)
            index = end
        elif pair == "/*":
            active[index : index + 2] = "  "
            block_depth = 1
            index += 2
        else:
            index += 1
    return "".join(active)


def _anchor_slice(locator: Locator, root: Path, claim_id: str) -> Occurrence:
    resolved, canonical = _resource(locator.path, root, "claim anchor")
    text = (
        resolved.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    )
    token = f"<{locator.identity}>"
    matches = list(re.finditer(re.escape(token), _active_typst_source(text)))
    if len(matches) != 1:
        _fail(f"{canonical} must contain exactly one {token} anchor occurrence")
    match = matches[0]
    start = text.rfind("\n\n", 0, match.start())
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", match.end())
    end = len(text) if end < 0 else end
    accepted_text = (
        text[start : match.start()] + text[match.end() : end]
    ).strip()
    accepted = accepted_text.encode("utf-8") + b"\n"
    start_byte = len(text[:start].encode("utf-8"))
    end_byte = len(text[:end].encode("utf-8"))
    anchor_match = ANCHOR.fullmatch(locator.raw)
    assert anchor_match
    anchored_claim = anchor_match.group(4)
    if anchored_claim != claim_id:
        _fail(f"{claim_id} locator points at another claim's anchor")
    return Occurrence(
        canonical,
        locator.identity,
        claim_id,
        anchor_match.group(3),
        start_byte,
        end_byte,
        hashlib.sha256(accepted).hexdigest(),
    )


def _occurrences(claims: tuple[Claim, ...], root: Path) -> tuple[Occurrence, ...]:
    result: list[Occurrence] = []
    for claim in claims:
        current = tuple(
            _anchor_slice(locator, root, claim.id)
            for locator in (claim.owner, claim.falsifier, *claim.limitations)
        )
        if len({item.canonical_span for item in current}) != len(current):
            _fail(
                f"{claim.id} owner, falsifier, and limitation must resolve to distinct canonical slices"
            )
        result.extend(current)
    return tuple(result)


def legal_transition(kind: str, from_state: str, to_state: str) -> bool:
    """Return whether a state transition is legal before authentication."""
    if kind == "advisory":
        return from_state == to_state
    return (from_state, to_state) in LEGAL_TRANSITIONS.get(kind, frozenset())


def _receipt(
    record: Mapping[str, object],
    root: Path,
    claims: Mapping[str, Claim],
    occurrences: Mapping[tuple[str, str], Occurrence],
    index: int,
    verifier: ReceiptVerifier | None,
    repository_revision: str | None,
) -> Receipt:
    allowed = {
        "id",
        "claim_id",
        "kind",
        "from",
        "to",
        "principal",
        "authentication",
        "verdict",
        "locator",
        "accepted_sha256",
        "repository_revision",
        "reviewed_at",
    }
    if set(record) != allowed:
        _fail(f"receipt {index} has an invalid key set")
    rid = _string(record["id"], f"receipt {index}.id")
    claim_id = _string(record["claim_id"], f"{rid}.claim_id")
    if claim_id not in claims:
        _fail(f"{rid} references an unknown claim")
    kind = _string(record["kind"], f"{rid}.kind")
    from_state, to_state = (
        _string(record["from"], f"{rid}.from"),
        _string(record["to"], f"{rid}.to"),
    )
    principal = _string(record["principal"], f"{rid}.principal")
    authentication = _string(record["authentication"], f"{rid}.authentication")
    verdict = _string(record["verdict"], f"{rid}.verdict")
    revision = _string(record["repository_revision"], f"{rid}.repository_revision")
    if (
        kind not in RECEIPT_KINDS
        or authentication not in AUTHENTICATION
        or not IDENTITY.fullmatch(rid)
        or not REVISION.fullmatch(revision)
    ):
        _fail(
            f"{rid} has an illegal receipt identity, kind, authentication, or revision"
        )
    if not RECEIPT_TIME.fullmatch(_string(record["reviewed_at"], f"{rid}.reviewed_at")):
        _fail(f"{rid}.reviewed_at is malformed")
    digest = _string(record["accepted_sha256"], f"{rid}.accepted_sha256")
    if not SHA256.fullmatch(digest):
        _fail(f"{rid}.accepted_sha256 is malformed")
    locator = _locator(record["locator"], root, f"{rid}.locator", "receipt")
    claim = claims[claim_id]
    if (locator.path, locator.identity) != (claim.owner.path, claim.owner.identity):
        _fail(f"{rid} replays a locator outside its claim owner section")
    occurrence = occurrences.get((locator.path, locator.identity))
    if occurrence is None or occurrence.claim_id != claim_id:
        _fail(f"{rid} replays a locator outside its claim section")
    if occurrence.accepted_sha256 != digest:
        _fail(f"{rid} accepted bytes changed or belong to the wrong section")
    if not legal_transition(kind, from_state, to_state):
        _fail(f"{rid} is not a legal {kind} transition")
    state_changing = from_state != to_state
    authenticated = False
    if state_changing:
        if authentication == "manual":
            _fail(f"{rid} manual assertions cannot promote or release")
        if repository_revision is None or revision != repository_revision:
            _fail(f"{rid} is not bound to the current repository revision")
        attestation = ReceiptAttestation(
            claim_id,
            kind,
            from_state,
            to_state,
            digest,
            principal,
            revision,
            authentication,
        )
        if verifier is None or verifier(attestation) is not True:
            _fail(f"{rid} has no verified immutable authentication attestation")
        authenticated = True
    if kind == "advisory":
        if verdict != "advisory":
            _fail(f"{rid} advisory verdict must remain advisory")
    elif verdict != to_state:
        _fail(f"{rid} verdict must equal the transition destination")
    return Receipt(
        rid,
        claim_id,
        kind,
        from_state,
        to_state,
        principal,
        authentication,
        verdict,
        locator,
        digest,
        revision,
        authenticated,
    )


def validate_ledger(
    data: Mapping[str, object],
    root: Path = ROOT,
    *,
    receipt_verifier: ReceiptVerifier | None = None,
    repository_revision: str | None = None,
) -> PrincipalClaims:
    """Validate the ledger and return the typed consumer model."""
    if set(data) != {"schema", "claims", "receipts"} or data.get("schema") != SCHEMA:
        _fail("ledger must contain schema, claims, and receipts for the v2 contract")
    raw_claims, raw_receipts = data.get("claims"), data.get("receipts")
    if (
        not isinstance(raw_claims, list)
        or not raw_claims
        or not isinstance(raw_receipts, list)
    ):
        _fail("claims and receipts must be arrays of tables")
    claims = tuple(
        _claim(_mapping(item, "claim"), root, index)
        for index, item in enumerate(raw_claims)
    )
    by_id = {claim.id: claim for claim in claims}
    if len(by_id) != len(claims):
        _fail("claim IDs must be unique")
    prose_resources = {
        locator.path
        for claim in claims
        for locator in (claim.owner, claim.falsifier, *claim.limitations)
    }
    for claim in claims:
        if any(
            evidence.role == "empirical"
            and evidence.locator.path in prose_resources
            for evidence in claim.evidence
        ):
            _fail(f"{claim.id} empirical evidence must not alias a claim prose resource")
    occurrences = _occurrences(claims, root)
    occurrence_map = {(item.surface, item.anchor): item for item in occurrences}
    receipts = tuple(
        _receipt(
            _mapping(item, "receipt"),
            root,
            by_id,
            occurrence_map,
            index,
            receipt_verifier,
            repository_revision,
        )
        for index, item in enumerate(raw_receipts)
    )
    if len({receipt.id for receipt in receipts}) != len(receipts):
        _fail("receipt IDs must be unique")
    for claim in claims:
        dimensions = {
            "maturity": claim.maturity,
            "review": claim.review_state,
            "release": claim.release_state,
        }
        for kind, current in dimensions.items():
            previous = INITIAL_STATES[kind]
            sequence = [
                item
                for item in receipts
                if item.claim_id == claim.id and item.kind == kind
            ]
            for item in sequence:
                if item.from_state != previous:
                    _fail(f"{item.id} does not continue the {kind} transition sequence")
                previous = item.to_state
            if previous != current:
                _fail(f"{claim.id} current {kind} state does not match its receipts")
        if claim.release_state == "admissible" and not any(
            item.claim_id == claim.id
            and item.kind == "release"
            and item.to_state == "admissible"
            and item.authenticated
            for item in receipts
        ):
            _fail(f"{claim.id} has no authenticated release receipt")
    payload = repr((claims, occurrences, receipts)).encode("utf-8")
    return PrincipalClaims(
        claims, receipts, occurrences, hashlib.sha256(payload).hexdigest()
    )


def _repository_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    if result.returncode or not REVISION.fullmatch(revision):
        _fail("repository revision is unavailable for receipt validation")
    return revision


def read_principal_claims(
    path: Path = DEFAULT_LEDGER,
    root: Path = ROOT,
    *,
    receipt_verifier: ReceiptVerifier | None = None,
    repository_revision: str | None = None,
) -> PrincipalClaims:
    """Read and validate the TOML ledger."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    receipts = data.get("receipts")
    if repository_revision is None and isinstance(receipts, list) and receipts:
        repository_revision = _repository_revision(root)
    return validate_ledger(
        data,
        root,
        receipt_verifier=receipt_verifier,
        repository_revision=repository_revision,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    model = read_principal_claims(args.ledger, ROOT)
    print(
        f"validated {len(model.claims)} principal claims and {len(model.receipts)} receipts"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
