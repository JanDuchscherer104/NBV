from __future__ import annotations

import sys
from pathlib import Path

import tempfile
import unittest
import json

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
        assert classify_reference(".agents/memory/transcripts/user/2026/08/messages.jsonl") == "transcript-provenance"
        assert classify_reference(".agents/archive/docs/old.md") == "archive-provenance"
        assert classify_reference(".agents/resolved.toml") == "resolved-provenance"
        assert classify_reference(".omx/plans/migration-receipt.json") == "migration-receipt"
        assert any("live" in str(e) for e in validate_reference_classes([{"path": ".agents/memory/state/DECISIONS.md"}]))


    def test_transcript_and_debrief_cannot_be_generic_decision_sinks(self) -> None:
        errors = validate_no_generic_sinks([("transcript.jsonl", 'promotion_target: .agents/memory/state/DECISIONS.md')])
        assert errors

    def test_historical_transcript_sink_is_ignored_by_repository_scan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "transcript.jsonl"
            path.write_text("promotion_target: .agents/memory/state/DECISIONS.md", encoding="utf-8")
            assert validate_repository_sinks(root, [{"path": "transcript.jsonl", "classification": "transcript-provenance"}]) == []


    def test_theory_matrix_covers_every_page(self) -> None:
        rows = [{"path": "a.qmd", "classification": "thin", "canonical_destination": "thesis.typ", "inbound_links": [], "citation_disposition": "retain"}]
        assert validate_theory_matrix(rows, ["a.qmd", "b.qmd"])


    def test_expected_page_manifest_is_exact(self) -> None:
        manifest = {"expected_pages": ["index.html", "api.html"]}
        assert validate_expected_pages(manifest, ["api.html", "index.html"]) == []
        assert validate_expected_pages(manifest, ["index.html", "questions.html"])


    def test_typst_contract_can_be_marked_future_integration(self) -> None:
        assert validate_typst_contract("", future_integration=True) == []
        assert validate_typst_contract("", future_integration=False)


if __name__ == "__main__":
    unittest.main()
