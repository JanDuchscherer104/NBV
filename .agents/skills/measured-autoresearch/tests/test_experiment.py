import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "experiment.py"
SPEC = importlib.util.spec_from_file_location("experiment", SCRIPT)
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


class ExperimentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.mission = Path(self.temp.name) / "mission"
        self.mission.mkdir()
        self.contract_source = self.mission / "input.json"
        self.contract_source.write_text(json.dumps(experiment.EXAMPLE_CONTRACT))
        experiment.command_init(self.args(contract=self.contract_source))
        self.contract = json.loads((self.mission / "measurements" / "contract.json").read_text())

    def tearDown(self):
        self.temp.cleanup()

    def args(self, **values):
        return type("Args", (), {"mission_root": self.mission, **values})()

    def result(self, iteration, candidate, loss, runtime=10.0, status="valid", gates=None):
        run = self.mission / "measurements" / "runs" / f"{iteration:04d}-{candidate}"
        run.mkdir(parents=True)
        artifact = run / "artifact-manifest.json"
        kinds = ["ownership_snapshot"] if iteration == 0 else ["ownership_snapshot", "candidate_patch", "restore_proof"]
        artifacts = []
        for kind in kinds:
            path = run / f"{kind}.json"
            path.write_text("{}\n")
            artifacts.append({
                "kind": kind, "path": str(path.relative_to(self.mission)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size_bytes": path.stat().st_size, "provenance": "unit test",
            })
        artifact.write_text(json.dumps({"artifacts": artifacts}) + "\n")
        value = dict(experiment.EXAMPLE_RESULT)
        value.update({
            "contract_id": self.contract["contract_id"],
            "evaluator_fingerprint": self.contract["evaluator"]["fingerprint"],
            "iteration": iteration, "candidate": candidate, "revision": f"r{iteration}",
            "hypothesis": candidate, "metrics": {"loss": loss, "runtime_s": runtime},
            "gates": {"tests": True} if gates is None else gates, "status": status,
            "artifact": str(artifact.relative_to(self.mission)),
        })
        source = run / "result.json"
        source.write_text(json.dumps(value))
        return source

    def append(self, *args, **kwargs):
        experiment.command_append(self.args(result=self.result(*args, **kwargs)))

    def test_tracks_baseline_keep_discard_and_reports_svg(self):
        self.append(0, "baseline", 1.0)
        self.append(1, "better", 0.8)
        self.append(2, "worse", 0.9)
        rows = experiment.validate_rows(self.mission / "measurements", self.contract)
        self.assertEqual([row["decision"] for row in rows], ["baseline", "keep", "discard"])
        self.assertEqual(rows[2]["reference_revision"], "r1")
        experiment.command_report(self.args())
        root = self.mission / "measurements"
        self.assertIn("<svg", (root / "progress.svg").read_text())
        self.assertEqual(json.loads((root / "summary.json").read_text())["rows"], 3)

    def test_rejects_stale_contract(self):
        source = self.result(0, "baseline", 1.0)
        value = json.loads(source.read_text())
        value["contract_id"] = "stale"
        source.write_text(json.dumps(value))
        with self.assertRaises(SystemExit):
            experiment.command_append(self.args(result=source))

    def test_rejects_missing_gate_and_unsafe_command(self):
        with self.assertRaises(SystemExit):
            experiment.command_append(self.args(result=self.result(0, "baseline", 1.0, gates={})))
        unsafe = dict(experiment.EXAMPLE_CONTRACT)
        unsafe["evaluator"] = {"command": "rm -rf /", "fingerprint": "x"}
        with self.assertRaises(SystemExit):
            experiment.validate_contract(unsafe)

    def test_rejects_artifact_escape(self):
        source = self.result(0, "baseline", 1.0)
        value = json.loads(source.read_text())
        value["artifact"] = "../outside.json"
        source.write_text(json.dumps(value))
        with self.assertRaises(SystemExit):
            experiment.command_append(self.args(result=source))

    def test_validation_rejects_tampered_decision(self):
        self.append(0, "baseline", 1.0)
        self.append(1, "better", 0.8)
        ledger = self.mission / "measurements" / "experiments.tsv"
        ledger.write_text(ledger.read_text().replace("\tkeep\tprimary_improved\t", "\tdiscard\tprimary_improved\t"))
        with self.assertRaises(SystemExit):
            experiment.validate_rows(self.mission / "measurements", self.contract)

    def test_validation_rejects_unknown_status_and_bad_manifest(self):
        self.append(0, "baseline", 1.0)
        ledger = self.mission / "measurements" / "experiments.tsv"
        ledger.write_text(ledger.read_text().replace("\tvalid\tbaseline\t", "\tweird\tbaseline\t"))
        with self.assertRaises(SystemExit):
            experiment.validate_rows(self.mission / "measurements", self.contract)
        manifest = self.mission / "measurements" / "runs" / "0000-baseline" / "artifact-manifest.json"
        manifest.write_text("{}\n")
        with self.assertRaises(SystemExit):
            experiment.validate_manifest(self.mission / "measurements", "measurements/runs/0000-baseline/artifact-manifest.json", self.contract)

    def test_manifest_rejects_wrong_content_hash(self):
        run = self.mission / "measurements" / "runs" / "hash-check"
        run.mkdir(parents=True)
        sample = run / "sample.bin"
        sample.write_bytes(b"measured")
        manifest = run / "artifact-manifest.json"
        manifest.write_text(json.dumps({"artifacts": [{
            "kind": "sample", "path": str(sample.relative_to(self.mission)), "sha256": "0" * 64,
            "size_bytes": sample.stat().st_size, "provenance": "unit test",
        }]}))
        with self.assertRaises(SystemExit):
            experiment.validate_manifest(
                self.mission / "measurements",
                str(manifest.relative_to(self.mission)), self.contract,
            )

    def test_uses_ordered_secondary_and_allowed_regression(self):
        self.append(0, "baseline", 1.0, runtime=10.0)
        self.append(1, "faster-tie", 1.0, runtime=9.9)
        self.append(2, "slow-primary-win", 0.8, runtime=10.2)
        rows = experiment.validate_rows(self.mission / "measurements", self.contract)
        self.assertEqual(rows[1]["decision_reason"], "secondary_improved:runtime_s")
        self.assertEqual(rows[2]["decision_reason"], "disallowed_regression:runtime_s")

    def test_reports_plateau_after_three_discards(self):
        self.append(0, "baseline", 1.0)
        self.append(1, "one", 1.1)
        self.append(2, "two", 1.1)
        self.append(3, "three", 1.1)
        experiment.command_report(self.args())
        summary = json.loads((self.mission / "measurements" / "summary.json").read_text())
        self.assertTrue(summary["plateau"])


if __name__ == "__main__":
    unittest.main()
