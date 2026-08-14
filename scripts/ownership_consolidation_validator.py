#!/usr/bin/env python3
"""Regression gates for the ARIA-NBV ownership-consolidation migration.

The validator consumes small JSON artifacts produced by the inventory/migration
lane.  It deliberately does not discover or rewrite repository content: source
owners remain authoritative and this module only checks their receipts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

LEDGER_DISPOSITIONS = {
    "removed", "historical", "code-owned", "test-owned", "literature-owned",
    "deferred-action",
}
ALLOWED_REFERENCE_CLASSES = {
    "dated-history",
    "archive-provenance",
    "resolved-provenance",
    "migration-receipt",
}
THEORY_CLASSES = {"deprecated", "keep", "thin", "delete"}
INVENTORY_DISPOSITIONS = LEDGER_DISPOSITIONS | {"unresolved"}
AGENTS_DB_MARKERS = ("agents-db", ".agents/issues.toml", ".agents/todos.toml", ".agents/refactors.toml")
RETIRED_SOURCE_PATHS = {
    "docs/contents/thesis/roadmap.qmd",
    "docs/contents/thesis/questions.qmd",
    "docs/contents/thesis/m1_contract_report.qmd",
    ".agents/memory/state/PROJECT_STATE.md",
    ".agents/memory/state/DECISIONS.md",
    ".agents/memory/state/GOTCHAS.md",
    ".agents/memory/state/OPEN_QUESTIONS.md",
}
LEGACY_MARKERS = ("roadmap.qmd", "questions.qmd", "m1_contract_report.qmd", "PROJECT_STATE.md", "DECISIONS.md", "GOTCHAS.md", "OPEN_QUESTIONS.md")
KNOWN_MIGRATION_RECEIPTS = {
    ".omx/specs/ownership-branch-consolidation-inventory.json",
    ".omx/specs/ownership-branch-consolidation-inventory.md",
}
RESOLVED_PROVENANCE_PATHS = {
    ".agents/AGENTS_INTERNAL_DB.md",
    ".agents/issues.toml",
    ".agents/todos.toml",
    ".agents/memory/README.md",
    ".agents/refactors.toml",
    ".agents/references/source_order.md",
    ".agents/resolved.toml",
    ".agents/skills/agents-db/SKILL.md",
    ".agents/skills/aria-grill/SKILL.md",
    ".agents/skills/aria-grill/references/upstream-mattpocock.md",
    ".agents/skills/aria-nbv-context/references/context_map.md",
    ".agents/skills/aria-nbv-context/scripts/nbv_context_index.sh",
    ".graphifyignore",
    "aria_nbv/tests/agent_memory/test_codex_transcript_extract.py",
    "scripts/codex_transcript_extract.py",
    "scripts/new_debrief.py",
}


@dataclass(frozen=True)
class ValidationError:
    item: str
    message: str

    def __str__(self) -> str:
        return f"{self.item}: {self.message}"


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_migration_ledger(rows: Iterable[dict[str, Any]], root: Path, *, full: bool = False, materialize: bool = True, enforce_readiness: bool = True) -> list[ValidationError]:
    """Validate row schema, coverage metadata, and materialized destinations."""
    errors: list[ValidationError] = []
    seen: set[str] = set()
    required = {"id", "source", "disposition", "canonical_destination", "destination_verified"}
    if full:
        required |= {"source_blob_id", "destination_locator", "link_action"}
    for index, row in enumerate(rows):
        item = str(row.get("id", f"row-{index}"))
        missing = sorted(required - row.keys())
        if missing:
            errors.append(ValidationError(item, f"missing fields: {', '.join(missing)}"))
            continue
        if item in seen:
            errors.append(ValidationError(item, "duplicate row id"))
        seen.add(item)
        if full and (not re.fullmatch(r"[0-9a-f]{40}", str(row.get("source_blob_id", "")))):
            errors.append(ValidationError(item, "source_blob_id must be a Git blob SHA"))
        disposition = row["disposition"]
        if disposition not in INVENTORY_DISPOSITIONS:
            errors.append(ValidationError(item, f"unknown disposition: {disposition!r}"))
        destination = row["canonical_destination"]
        if disposition != "removed":
            if not _nonempty(destination):
                errors.append(ValidationError(item, "canonical_destination is required"))
            elif any(marker in destination for marker in AGENTS_DB_MARKERS):
                errors.append(ValidationError(item, "agents-DB cannot be the canonical destination"))
            elif materialize and not (root / destination.split("#", 1)[0]).is_file():
                errors.append(ValidationError(item, f"canonical destination does not exist: {destination}"))
            if enforce_readiness and row["destination_verified"] is not True:
                errors.append(ValidationError(item, "destination_verified must be true before deletion"))
            if not _nonempty(row.get("destination_locator")):
                errors.append(ValidationError(item, "destination_locator is required for materialized content"))
        elif not isinstance(row["destination_verified"], bool):
            errors.append(ValidationError(item, "destination_verified must be boolean"))
        if disposition == "deferred-action":
            for field in ("backlog_id", "owner", "gate"):
                if not _nonempty(row.get(field)):
                    errors.append(ValidationError(item, f"{field} is required for deferred-action"))
            if row.get("tracking_record", "").find("follow-up only after canonical content is materialized") < 0:
                errors.append(ValidationError(item, "deferred tracking_record must be post-migration-only"))
        if disposition == "removed" and not _nonempty(row.get("removal_evidence")):
            errors.append(ValidationError(item, "removal_evidence is required"))
    return errors


def classify_reference(path: str, *, resolved: bool = False, receipt: bool = False) -> str:
    """Classify a legacy-state reference; live references are rejected by callers."""
    normalized = path.replace("\\", "/")
    if receipt or normalized.startswith(".omx/specs/") or normalized.startswith(".omx/") and ("receipt" in normalized or "migration" in normalized):
        return "migration-receipt"
    if resolved or normalized.startswith(".agents/resolved"):
        return "resolved-provenance"
    if "/transcripts/" in normalized or normalized.startswith(".agents/memory/transcripts/"):
        return "resolved-provenance"
    if normalized.startswith("docs/typst/thesis_slides/"):
        return "dated-history"
    if normalized.startswith(".agents/archive/") or "/archive/" in normalized:
        return "archive-provenance"
    if "/history/" in normalized:
        return "dated-history"
    return "live-reference"


def _normalized_path(path: str, root: Path) -> str | None:
    """Return a repository-relative path, rejecting traversal and absolutes."""
    candidate = Path(path.replace("\\", "/"))
    if candidate.is_absolute():
        return None
    root = root.resolve()
    try:
        return (root / candidate).resolve().relative_to(root).as_posix()
    except ValueError:
        return None


def _is_tracked_file(root: Path, relative: str) -> bool:
    candidate = root / relative
    if not candidate.is_file():
        return False
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == relative


def _file_digests(root: Path, relative: str) -> tuple[str, str] | None:
    candidate = root / relative
    if not candidate.is_file():
        return False
    git_hash = subprocess.run(["git", "hash-object", str(candidate)], cwd=root, capture_output=True, text=True)
    if git_hash.returncode != 0:
        return None
    return git_hash.stdout.strip(), hashlib.sha256(candidate.read_bytes()).hexdigest()


def _frozen_provenance_receipts(root: Path) -> dict[str, dict[str, str]]:
    """Load the exact path/class receipt set frozen by the migration inventory."""
    inventory = root / ".omx/specs/ownership-branch-consolidation-inventory.json"
    try:
        data = json.loads(inventory.read_text(encoding="utf-8"))
        refs = data["consumer_inventory"]["references"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return {}
    return {
        str(ref["path"]): ref
        for ref in refs
        if isinstance(ref, dict) and isinstance(ref.get("path"), str) and isinstance(ref.get("classification"), str)
        and isinstance(ref.get("blob_oid"), str) and isinstance(ref.get("content_sha256"), str)
    }


def _bounded_provenance(path: str, classification: str, root: Path) -> bool:
    normalized = _normalized_path(path, root)
    if normalized is None:
        return False
    frozen = _frozen_provenance_receipts(root)
    if normalized in frozen:
        receipt = frozen[normalized]
        frozen_class = str(receipt["classification"])
        compatible = frozen_class == classification or {frozen_class, classification} == {"dated-history", "archive-provenance"}
        if normalized == ".omx/specs/ownership-branch-consolidation-inventory.json":
            return compatible and normalized in KNOWN_MIGRATION_RECEIPTS and _is_tracked_file(root, normalized)
        digests = _file_digests(root, normalized)
        return compatible and digests is not None and digests == (receipt["blob_oid"], receipt["content_sha256"])
    return False


def validate_reference_classes(references: Iterable[dict[str, Any]], root: Path = Path.cwd()) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for index, ref in enumerate(references):
        path = str(ref.get("path", f"reference-{index}"))
        if ref.get("classification") == "live-reference":
            errors.append(ValidationError(path, "live-reference classification is not allowed"))
            continue
        normalized = _normalized_path(path, root)
        inferred = classify_reference(normalized or path, resolved=bool(ref.get("resolved")), receipt=bool(ref.get("receipt"))) if normalized else "live-reference"
        classification = inferred
        if inferred == "live-reference" and ref.get("classification") == "resolved-provenance":
            candidate = root / normalized if normalized else root / "__invalid__"
            if candidate.is_file() and _is_tracked_file(root, normalized) and normalized not in RETIRED_SOURCE_PATHS and not any(marker in candidate.read_text(encoding="utf-8") for marker in LEGACY_MARKERS):
                classification = "resolved-provenance"
        if classification not in ALLOWED_REFERENCE_CLASSES or not _bounded_provenance(path, classification, root):
            errors.append(ValidationError(path, "live legacy-state reference is not allowed"))
    return errors


def validate_no_generic_sinks(texts: Iterable[tuple[str, str]]) -> list[ValidationError]:
    """Reject transcript/debrief promotion sinks that create a second authority."""
    errors: list[ValidationError] = []
    forbidden = ("promotion_target: .agents/memory/state", "canonical destination: .agents/memory/state", "DECISIONS.md")
    for path, text in texts:
        if "transcript" not in path and "debrief" not in path:
            continue
        for marker in forbidden:
            if marker.lower() in text.lower():
                errors.append(ValidationError(path, f"generic sink marker found: {marker}"))
    return errors


def validate_theory_matrix(rows: Iterable[dict[str, Any]], theory_paths: Iterable[str]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    actual = set(theory_paths)
    seen: set[str] = set()
    for row in rows:
        path = str(row.get("path", "<missing-path>"))
        seen.add(path)
        if row.get("classification") not in THEORY_CLASSES:
            errors.append(
                ValidationError(
                    path, "classification must be deprecated, keep, thin, or delete"
                )
            )
        if row.get("classification") != "delete" and not _nonempty(row.get("canonical_destination")):
            errors.append(ValidationError(path, "retained page requires canonical_destination"))
        if not isinstance(row.get("inbound_links"), list) or not isinstance(row.get("citation_disposition"), str):
            errors.append(ValidationError(path, "inbound_links and citation_disposition are required"))
    for missing in sorted(actual - seen):
        errors.append(ValidationError(missing, "theory page missing from matrix"))
    return errors


def validate_theory_topology(rows: Iterable[dict[str, Any]], root: Path) -> list[ValidationError]:
    """Require retained theory pages to remain deprecated docs-owned pointers."""
    errors: list[ValidationError] = []
    forbidden = re.compile(r"\b(?:canonical|current)\s+(?:theory|implementation|source)\s+owner\b|\bowns?\s+(?:theory|implementation contract)\b", re.IGNORECASE)
    for row in rows:
        path = str(row.get("path", "<missing-path>"))
        normalized = _normalized_path(path, root)
        if normalized is None:
            errors.append(
                ValidationError(path, "theory path must be repository-relative")
            )
            continue
        candidate = root / normalized
        if not candidate.is_file():
            errors.append(ValidationError(path, "theory page does not exist"))
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(ValidationError(path, f"theory page is not valid UTF-8: {exc}"))
            continue
        frontmatter = text.split("\n---\n", 1)[0] if text.startswith("---\n") else ""
        for key, expected in (("phase", "archive"), ("status", "deprecated"), ("owner", "docs")):
            if not re.search(rf"(?m)^{key}:\s*{re.escape(expected)}\s*$", frontmatter):
                errors.append(ValidationError(path, f"frontmatter {key} must be {expected!r}"))
        if forbidden.search(text):
            errors.append(ValidationError(path, "deprecated theory page contains an ownership claim"))
        expected_hash = row.get("content_sha256")
        actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            errors.append(ValidationError(path, "content_sha256 does not match file"))
    return errors


def validate_expected_pages(manifest: dict[str, Any], actual_pages: Iterable[str]) -> list[ValidationError]:
    expected = manifest.get("expected_pages")
    if not isinstance(expected, list) or not all(isinstance(p, str) for p in expected):
        return [ValidationError("manifest", "expected_pages must be a string list")]
    actual = sorted(set(actual_pages))
    wanted = sorted(set(expected))
    return [] if actual == wanted else [ValidationError("manifest", f"page mismatch: expected {wanted}, got {actual}")]


def validate_consumer_inventory(inventory: dict[str, Any]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    refs = inventory.get("references")
    if not isinstance(refs, list):
        return [ValidationError("consumer_inventory", "references must be a list")]
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            errors.append(ValidationError(f"consumer[{index}]", "must be an object"))
            continue
        for field in ("path", "locators", "classification", "consumer_type", "disposition", "replacement_owner"):
            if field not in ref:
                errors.append(ValidationError(f"consumer[{index}]", f"missing field: {field}"))
        if not isinstance(ref.get("locators"), list) or not ref.get("locators"):
            errors.append(ValidationError(f"consumer[{index}]", "locators must be non-empty"))
        if ref.get("classification") not in ALLOWED_REFERENCE_CLASSES | {"live-reference"}:
            errors.append(ValidationError(f"consumer[{index}]", "invalid classification"))
    counts = inventory.get("class_counts")
    observed: dict[str, int] = {}
    for ref in refs:
        if isinstance(ref, dict) and isinstance(ref.get("classification"), str):
            observed[ref["classification"]] = observed.get(ref["classification"], 0) + 1
    if not isinstance(counts, dict) or counts != observed:
        errors.append(ValidationError("consumer_inventory", "class_counts do not match reference count"))
    if inventory.get("reference_count") != len(refs):
        errors.append(ValidationError("consumer_inventory", "reference_count mismatch"))
    return errors


def validate_source_blobs(rows: Iterable[dict[str, Any]], root: Path, *, receipt_commit: str | None = None) -> list[ValidationError]:
    """Ensure each source receipt still names the exact current Git blob."""
    errors: list[ValidationError] = []
    for row in rows:
        revisions = ["HEAD"]
        if receipt_commit:
            revisions.append(receipt_commit)
        actual = ""
        for revision in revisions:
            result = subprocess.run(["git", "rev-parse", f"{revision}:{row['source']}"], cwd=root, capture_output=True, text=True)
            if result.returncode == 0:
                actual = result.stdout.strip()
                if actual == row.get("source_blob_id"):
                    break
        if actual != row.get("source_blob_id"):
            errors.append(ValidationError(str(row.get("id", row.get("source"))), "source_blob_id does not match current Git blob"))
    return errors


def validate_repository_sinks(root: Path, refs: Iterable[dict[str, Any]]) -> list[ValidationError]:
    texts: list[tuple[str, str]] = []
    paths = {ref.get("path") for ref in refs if isinstance(ref, dict) and isinstance(ref.get("path"), str)}
    tracked = subprocess.run(["git", "ls-files", "--", ".agents/memory/transcripts", ".agents/memory/history", ".agents/archive", ".omx/specs"], cwd=root, capture_output=True, text=True)
    if tracked.returncode == 0:
        paths.update(line.strip() for line in tracked.stdout.splitlines() if line.strip())
    errors: list[ValidationError] = []
    frozen = _frozen_provenance_receipts(root)
    for path in sorted(paths):
        classification = str(frozen[path]["classification"]) if path in frozen else classify_reference(path)
        bounded = classification in ALLOWED_REFERENCE_CLASSES and _bounded_provenance(path, classification, root)
        if path in frozen and not bounded:
            errors.append(ValidationError(path, "frozen provenance receipt blob/hash mismatch"))
            continue
        candidate = root / path
        if not candidate.is_file() or bounded:
            continue
        if candidate.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".gz", ".bin"}:
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(ValidationError(path, f"provenance candidate is not valid UTF-8: {exc}"))
            continue
        texts.append((path, text))
        if re.search(r"(?im)(?:promotion[_ ]target|canonical(?:[_ ]destination)?|canonical_updates_needed)\s*[:=].*(?:roadmap\.qmd|questions\.qmd|m1_contract_report\.qmd|PROJECT_STATE\.md|DECISIONS\.md|GOTCHAS\.md|OPEN_QUESTIONS\.md)", text):
            errors.append(ValidationError(path, "unfrozen provenance contains retired-source marker"))
    errors.extend(validate_no_generic_sinks(texts))
    return errors


def validate_typst_contract(text: str, *, future_integration: bool = False) -> list[ValidationError]:
    required = ("development_only", "promotion_entry")
    missing = [name for name in required if name not in text]
    if missing and not future_integration:
        return [ValidationError("typst", f"missing contract marker(s): {', '.join(missing)}")]
    return []


def validate_inventory(data: dict[str, Any], *, mode: str = "schema", root: Path = Path.cwd()) -> list[ValidationError]:
    """Validate the frozen inventory schema, optionally enforcing deletion gates."""
    errors: list[ValidationError] = []
    required_sections = {"schema_version", "baseline", "disposition_ledger", "theory_qmd_matrix", "consumer_inventory", "python_docstring_coverage", "verification", "expected_pages_manifest"}
    for section in sorted(required_sections - data.keys()):
        errors.append(ValidationError("inventory", f"missing section: {section}"))
    baseline = data.get("baseline", {})
    if not isinstance(baseline, dict):
        errors.append(ValidationError("baseline", "must be an object"))
    else:
        for field in ("pr50_commit", "tree"):
            value = baseline.get(field)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
                errors.append(ValidationError("baseline", f"{field} must be a 40-character SHA"))
        if baseline.get("receipt_status") != "hosted-and-local-verification":
            errors.append(ValidationError("baseline", "receipt_status is not merged-baseline verified"))
    ledger = data.get("disposition_ledger", [])
    if not isinstance(ledger, list):
        errors.append(ValidationError("disposition_ledger", "must be a list"))
        ledger = []
    row_fields = {"source", "anchor", "lines", "subject", "disposition", "canonical_destination", "destination_verified", "link_action", "id", "source_blob_id", "destination_locator"}
    blockers: list[ValidationError] = []
    for index, row in enumerate(ledger):
        item = f"ledger[{index}]"
        if not isinstance(row, dict):
            errors.append(ValidationError(item, "must be an object"))
            continue
        missing = sorted(row_fields - row.keys())
        if missing:
            errors.append(ValidationError(item, f"missing fields: {', '.join(missing)}"))
        if row.get("disposition") not in INVENTORY_DISPOSITIONS:
            errors.append(ValidationError(item, f"unknown disposition: {row.get('disposition')!r}"))
        if not isinstance(row.get("destination_verified"), bool):
            errors.append(ValidationError(item, "destination_verified must be boolean"))
        if row.get("disposition") == "unresolved" or row.get("destination_verified") is False:
            blockers.append(ValidationError(item, "unresolved or destination not verified"))
    errors.extend(validate_migration_ledger(ledger, root=root, full=True, materialize=(mode == "deletion-ready"), enforce_readiness=(mode == "deletion-ready")))
    errors.extend(validate_source_blobs(ledger, root, receipt_commit=data.get("source_receipt_commit")))
    matrix = data.get("theory_qmd_matrix", [])
    if not isinstance(matrix, list):
        errors.append(ValidationError("theory_qmd_matrix", "must be a list"))
        matrix = []
    for index, row in enumerate(matrix):
        item = f"theory_qmd_matrix[{index}]"
        if not isinstance(row, dict):
            errors.append(ValidationError(item, "must be an object"))
            continue
        for field in ("path", "classification", "unique_role", "canonical_destination", "destination_verified", "inbound_links", "content_sha256"):
            if field not in row:
                errors.append(ValidationError(item, f"missing field: {field}"))
        if row.get("classification") not in THEORY_CLASSES:
            errors.append(ValidationError(item, "invalid classification"))
        if row.get("destination_verified") is False:
            blockers.append(ValidationError(item, "destination not verified"))
    errors.extend(validate_theory_matrix(matrix, [p.relative_to(root).as_posix() for p in (root / "docs/contents/theory").glob("*.qmd")]))
    errors.extend(validate_theory_topology(matrix, root))
    manifest = data.get("expected_pages_manifest", {})
    actual_pages = [p.relative_to(root / "docs").as_posix() for p in (root / "docs/contents").rglob("*.qmd")]
    errors.extend(validate_expected_pages(manifest, actual_pages))
    consumer = data.get("consumer_inventory", {})
    errors.extend(validate_consumer_inventory(consumer))
    if mode == "deletion-ready" and isinstance(consumer, dict):
        for ref in consumer.get("references", []):
            if isinstance(ref, dict) and ref.get("classification") == "live-reference":
                errors.append(ValidationError(str(ref.get("path", "reference")), "live-reference classification is not allowed in deletion-ready inventory"))
    sink_errors = validate_repository_sinks(root, consumer.get("references", []) if isinstance(consumer, dict) else [])
    if mode == "deletion-ready":
        errors.extend(sink_errors)
    if mode == "deletion-ready":
        errors.extend(validate_reference_classes(data.get("consumer_inventory", {}).get("references", []), root))
    consumers = data.get("consumer_inventory", {})
    if not isinstance(consumers, dict):
        errors.append(ValidationError("consumer_inventory", "must be an object"))
    elif mode == "deletion-ready" and consumers.get("unresolved_count", 0):
        blockers.append(
            ValidationError(
                "consumer_inventory",
                f"{consumers['unresolved_count']} unresolved live consumers",
            )
        )
    coverage = data.get("python_docstring_coverage", {})
    if not isinstance(coverage, dict):
        errors.append(ValidationError("python_docstring_coverage", "must be an object"))
    elif mode == "deletion-ready" and (
        coverage.get("status") != "verified"
        or coverage.get("destination_verified") is not True
    ):
        blockers.append(ValidationError("python_docstring_coverage", "coverage is not verified"))
    if mode == "deletion-ready":
        errors.extend(blockers)
    elif mode != "schema":
        errors.append(ValidationError("mode", f"unknown mode: {mode}"))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--mode", choices=("schema", "deletion-ready"), default="schema")
    args = parser.parse_args()
    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("inventory root must be an object")
        errors = validate_inventory(data, mode=args.mode, root=args.root.resolve())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        errors = [ValidationError("input", str(exc))]
    if errors:
        print(json.dumps({"status": "failed", "mode": args.mode, "errors": [error.__dict__ for error in errors]}, indent=2))
        return 1
    print(json.dumps({"status": "passed", "mode": args.mode}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
