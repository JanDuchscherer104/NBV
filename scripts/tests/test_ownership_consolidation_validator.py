from __future__ import annotations

import sys
from pathlib import Path

import tempfile
import unittest
import json
import hashlib
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ownership_consolidation_validator import (  # noqa: E402
    classify_reference,
    validate_expected_pages,
    validate_migration_ledger,
    validate_inventory,
    validate_consumer_inventory,
    validate_repository_sinks,
    validate_no_generic_sinks,
    validate_reference_classes,
    validate_theory_matrix,
    validate_typst_contract,
)


class OwnershipValidatorTests(unittest.TestCase):
    def test_frozen_inventory_schema_passes_without_deletion_readiness(self) -> None:
        inventory = json.loads((Path(__file__).parents[2] / ".omx/specs/ownership-branch-consolidation-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_inventory(inventory, mode="schema"), [])

    def test_frozen_inventory_deletion_mode_has_no_ledger_blockers(self) -> None:
        inventory = json.loads((Path(__file__).parents[2] / ".omx/specs/ownership-branch-consolidation-inventory.json").read_text(encoding="utf-8"))
        errors = validate_inventory(inventory, mode="deletion-ready")
        expected_ledger_blockers = [
            f"ledger[{index}]"
            for index, row in enumerate(inventory["disposition_ledger"])
            if row["disposition"] == "unresolved" or row["destination_verified"] is False
        ]
        error_items = {error.item for error in errors}
        self.assertFalse(expected_ledger_blockers)
        self.assertFalse(any(item.startswith("ledger[") for item in error_items))
        self.assertEqual(errors, [])

    def test_merged_baseline_receipt_requires_sha_and_tree(self) -> None:
        inventory = {"schema_version": 1, "baseline": {"pr50_commit": "bad", "tree": "bad", "receipt_status": "hosted-and-local-verification"}, "disposition_ledger": [], "theory_qmd_matrix": [], "consumer_inventory": {}, "python_docstring_coverage": {}, "verification": {}}
        errors = validate_inventory(inventory)
        self.assertEqual(sum("baseline" in str(error) for error in errors), 2)

    def test_frozen_inventory_has_no_agents_db_canonical_destinations(self) -> None:
        inventory = json.loads((Path(__file__).parents[2] / ".omx/specs/ownership-branch-consolidation-inventory.json").read_text(encoding="utf-8"))
        markers = (".agents/todos", ".agents/issues", ".agents/refactors", "agents-db", "backlog")
        destinations = [str(row.get("canonical_destination", "")) for row in inventory["disposition_ledger"]]
        self.assertFalse([destination for destination in destinations if any(marker in destination for marker in markers)])

    def test_consumer_classification_and_counts_must_match(self) -> None:
        inventory = {"references": [{"path": "x", "locators": [1], "classification": "live-reference", "consumer_type": "x", "disposition": "x", "replacement_owner": "x"}], "class_counts": {"dated-history": 1}, "reference_count": 1}
        errors = validate_consumer_inventory(inventory)
        self.assertTrue(any("class_counts" in str(error) for error in errors))

    def test_repository_sink_scan_is_wired_to_concrete_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "debrief.md"
            path.write_text("promotion_target: .agents/memory/state/DECISIONS.md", encoding="utf-8")
            self.assertTrue(validate_repository_sinks(root, [{"path": "debrief.md"}]))

    def test_materialized_destination_requires_existing_non_agents_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            (tmp_path / "owner.typ").write_text("content", encoding="utf-8")
            row = {"id": "q1", "source": "old.qmd", "disposition": "code-owned", "canonical_destination": "owner.typ", "destination_verified": True, "destination_locator": "section"}
            assert validate_migration_ledger([row], tmp_path) == []
            bad = {**row, "canonical_destination": ".agents/issues.toml"}
            assert any("agents-DB" in str(e) for e in validate_migration_ledger([bad], tmp_path))


    def test_missing_destination_is_rejected_before_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            row = {"id": "q1", "source": "old.qmd", "disposition": "test-owned", "canonical_destination": "missing.typ", "destination_verified": True, "destination_locator": "x"}
            assert any("does not exist" in str(e) for e in validate_migration_ledger([row], tmp_path))


    def test_reference_classifier_allows_only_provenance_classes(self) -> None:
        assert classify_reference(".agents/memory/history/2026/08/note.md") == "dated-history"
        assert classify_reference(".agents/memory/transcripts/user/2026/08/messages.jsonl") == "resolved-provenance"
        assert classify_reference(".agents/archive/docs/old.md") == "archive-provenance"
        assert classify_reference(".agents/resolved.toml") == "resolved-provenance"
        assert classify_reference(".omx/plans/migration-receipt.json") == "migration-receipt"
        assert any("live" in str(e) for e in validate_reference_classes([{"path": ".agents/memory/state/DECISIONS.md"}]))
        assert any("live" in str(e) for e in validate_reference_classes([{"path": ".agents/memory/state/DECISIONS.md", "classification": "transcript-provenance"}]))

    def test_retired_paths_and_boolean_flags_never_bypass_provenance(self) -> None:
        references = [
            {"path": ".agents/memory/state/DECISIONS.md", "receipt": True},
            {"path": ".agents/memory/state/PROJECT_STATE.md", "resolved": True},
            {"path": "README.md", "resolved": True},
            {"path": "AGENTS.md", "resolved": True},
            {"path": "docs/index.qmd", "resolved": True},
            {"path": ".agents/memory/transcripts/user/2026-05-09/user_messages.jsonl", "classification": "live-reference"},
        ]
        errors = validate_reference_classes(references, Path(__file__).parents[2])
        assert len(errors) == len(references)

    def test_reference_classifier_rejects_traversal_and_fake_provenance(self) -> None:
        references = [
            {"path": ".agents/memory/transcripts/../state/DECISIONS.md"},
            {"path": ".agents/archive/fake.md"},
            {"path": ".agents/memory/history/fake.md"},
            {"path": ".omx/specs/fake-receipt.json"},
        ]
        errors = validate_reference_classes(references, Path(__file__).parents[2])
        assert len(errors) == len(references)

    def test_new_tracked_looking_provenance_paths_are_not_frozen_receipts(self) -> None:
        references = [
            {"path": ".agents/memory/transcripts/user/2099-01-01/new.jsonl"},
            {"path": ".agents/memory/history/2099/01/new.md"},
            {"path": ".agents/archive/2099/new.md"},
            {"path": ".omx/specs/new-receipt.json"},
        ]
        errors = validate_reference_classes(references, Path(__file__).parents[2])
        assert len(errors) == len(references)

    def test_tracked_future_provenance_sink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in (".agents/memory/transcripts/2099/new.jsonl", ".agents/memory/history/2099/new.md", ".omx/specs/new.json"):
                path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("promotion_target: .agents/memory/state/DECISIONS.md\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            assert validate_repository_sinks(root, [])

    def test_modified_allowlisted_receipt_is_rejected_by_frozen_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / ".agents/memory/transcripts/2026/frozen.jsonl"
            path.parent.mkdir(parents=True); path.write_text("historical transcript\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True); subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
            oid = subprocess.check_output(["git", "hash-object", str(path)], cwd=root, text=True).strip()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            inv = root / ".omx/specs/ownership-branch-consolidation-inventory.json"; inv.parent.mkdir(parents=True)
            inv.write_text(json.dumps({"consumer_inventory": {"references": [{"path": ".agents/memory/transcripts/2026/frozen.jsonl", "classification": "resolved-provenance", "blob_oid": oid, "content_sha256": digest}]}}), encoding="utf-8")
            path.write_text("modified\n", encoding="utf-8")
            assert validate_repository_sinks(root, [])

    def test_inventory_uses_supplied_root_for_materialization(self) -> None:
        inventory = json.loads((Path(__file__).parents[2] / ".omx/specs/ownership-branch-consolidation-inventory.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            errors = validate_inventory(inventory, mode="deletion-ready", root=Path(directory))
        assert any("canonical destination does not exist" in str(error) for error in errors)


    def test_transcript_and_debrief_cannot_be_generic_decision_sinks(self) -> None:
        errors = validate_no_generic_sinks([("transcript.jsonl", 'promotion_target: .agents/memory/state/DECISIONS.md')])
        assert errors

    def test_untracked_transcript_sink_is_scanned_by_repository_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / ".agents" / "memory" / "transcripts" / "2026" / "transcript.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text("promotion_target: .agents/memory/state/DECISIONS.md", encoding="utf-8")
            assert validate_repository_sinks(root, [{"path": ".agents/memory/transcripts/2026/transcript.jsonl", "classification": "transcript-provenance"}])


    def test_theory_matrix_covers_every_page(self) -> None:
        rows = [{"path": "a.qmd", "classification": "thin", "canonical_destination": "thesis.typ", "inbound_links": [], "citation_disposition": "retain"}]
        assert validate_theory_matrix(rows, ["a.qmd", "b.qmd"])

    def test_theory_topology_rejects_current_owner_and_hash_drift(self) -> None:
        from ownership_consolidation_validator import validate_theory_topology
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.qmd"
            page.write_text("---\nphase: thesis\nstatus: current\nowner: theory\n---\nThis is the canonical theory owner.\n", encoding="utf-8")
            errors = validate_theory_topology([{"path": "page.qmd", "content_sha256": "0" * 64}], root)
        assert len(errors) >= 4

    def test_theory_topology_accepts_deprecated_docs_page_with_matching_hash(self) -> None:
        from hashlib import sha256
        from ownership_consolidation_validator import validate_theory_topology
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.qmd"
            page.write_text("---\nphase: archive\nstatus: deprecated\nowner: docs\n---\nExternal background only.\n", encoding="utf-8")
            digest = sha256(page.read_bytes()).hexdigest()
            assert validate_theory_topology([{"path": "page.qmd", "content_sha256": digest}], root) == []

    def test_binary_theory_page_fails_closed(self) -> None:
        from ownership_consolidation_validator import validate_theory_topology
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); page = root / "binary.qmd"
            page.write_bytes(b"---\nphase: archive\n\xff\xfe")
            errors = validate_theory_topology([{"path": "binary.qmd", "content_sha256": "0" * 64}], root)
        assert any("not valid UTF-8" in str(error) for error in errors)

    def test_binary_provenance_candidate_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / ".agents/memory/transcripts/2099/binary.jsonl"
            path.parent.mkdir(parents=True); path.write_bytes(b"\xff\xfe")
            errors = validate_repository_sinks(root, [{"path": ".agents/memory/transcripts/2099/binary.jsonl"}])
        assert any("not valid UTF-8" in str(error) for error in errors)


    def test_expected_page_manifest_is_exact(self) -> None:
        manifest = {"expected_pages": ["index.html", "api.html"]}
        assert validate_expected_pages(manifest, ["api.html", "index.html"]) == []
        assert validate_expected_pages(manifest, ["index.html", "questions.html"])


    def test_typst_contract_can_be_marked_future_integration(self) -> None:
        assert validate_typst_contract("", future_integration=True) == []
        assert validate_typst_contract("", future_integration=False)


if __name__ == "__main__":
    unittest.main()
