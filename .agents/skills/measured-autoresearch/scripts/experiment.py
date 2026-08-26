#!/usr/bin/env python3
"""Dependency-free experiment ledger and report generator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "1"
HEADER = [
    "schema", "contract_id", "timestamp_utc", "iteration", "candidate",
    "revision", "hypothesis", "reference_revision", "primary_value",
    "primary_delta", "primary_relation", "secondary_json", "gate_json",
    "runtime_s", "peak_memory_mb", "non_test_loc", "status", "decision",
    "decision_reason", "artifact",
]
REQUIRED_CONTRACT = {
    "evaluator", "data", "hard_gates", "primary", "secondary",
    "mutable_paths", "budget", "device", "seed", "output_paths", "rollback",
}
REQUIRED_RESULT = {
    "contract_id", "evaluator_fingerprint", "iteration", "candidate",
    "revision", "hypothesis", "metrics", "gates", "runtime_s",
    "peak_memory_mb", "non_test_loc", "status", "artifact",
}
UNSAFE = [
    r"\brm\s+-[^\n]*r[^\n]*f", r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-", r"\bgit\s+(checkout|restore)\s+--",
    r"\b(drop|truncate)\s+(database|table)\b", r"\bsudo\b",
    r"(?:token|password|secret|api[_-]?key)\s*=",
    r"https?://[^/\s:@]+:[^/\s@]+@",
]


def fail(message: str) -> "None":
    raise SystemExit(f"error: {message}")


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read JSON {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path} must contain a JSON object")
    return value


def measurement_root(mission: Path) -> Path:
    if not mission.is_dir():
        fail(f"mission root does not exist: {mission}")
    return mission.resolve() / "measurements"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_contract(contract: dict) -> dict:
    missing = sorted(REQUIRED_CONTRACT - contract.keys())
    if missing:
        fail(f"contract missing fields: {', '.join(missing)}")
    evaluator = contract.get("evaluator")
    if not isinstance(evaluator, dict) or not all(
        isinstance(evaluator.get(key), str) and evaluator[key].strip()
        for key in ("command", "fingerprint")
    ):
        fail("evaluator requires non-empty command and fingerprint")
    command = evaluator["command"]
    if "\n" in command or "\0" in command:
        fail("evaluator command must be one line")
    for pattern in UNSAFE:
        if re.search(pattern, command, re.IGNORECASE):
            fail(f"unsafe evaluator command matched {pattern!r}")
    primary = contract.get("primary")
    if not isinstance(primary, dict) or primary.get("direction") not in {"minimize", "maximize"}:
        fail("primary requires name and direction minimize|maximize")
    if not isinstance(primary.get("name"), str) or not primary["name"]:
        fail("primary requires a non-empty name")
    number(primary.get("tolerance"), "primary.tolerance", minimum=0)
    if not isinstance(contract["hard_gates"], list) or not all(
        isinstance(gate, str) and gate for gate in contract["hard_gates"]
    ):
        fail("hard_gates must be a list of names")
    if len(set(contract["hard_gates"])) != len(contract["hard_gates"]):
        fail("hard_gates must be unique")
    if not isinstance(contract["secondary"], list):
        fail("secondary must be a list")
    for index, metric in enumerate(contract["secondary"]):
        if not isinstance(metric, dict) or metric.get("direction") not in {"minimize", "maximize"}:
            fail(f"secondary[{index}] requires name and direction")
        if not isinstance(metric.get("name"), str) or not metric["name"]:
            fail(f"secondary[{index}] requires a name")
        number(metric.get("tolerance", 0), f"secondary[{index}].tolerance", minimum=0)
        number(metric.get("allowed_regression", 0), f"secondary[{index}].allowed_regression", minimum=0)
    names = [primary["name"], *(metric["name"] for metric in contract["secondary"])]
    if len(set(names)) != len(names):
        fail("primary and secondary metric names must be unique")
    for key in ("mutable_paths", "output_paths"):
        if not isinstance(contract[key], list) or not all(isinstance(value, str) and value for value in contract[key]):
            fail(f"{key} must be a list of paths")
    if not isinstance(contract["budget"], dict) or not contract["budget"]:
        fail("budget must be a non-empty object")
    for key in ("data", "device", "rollback"):
        if not isinstance(contract[key], str) or not contract[key].strip():
            fail(f"{key} must be a non-empty string")
    if isinstance(contract["seed"], bool) or not isinstance(contract["seed"], int):
        fail("seed must be an integer")
    normalized = json.loads(canonical(contract))
    normalized["schema_version"] = int(SCHEMA)
    normalized["evaluator"]["command_sha256"] = sha256(command)
    normalized["contract_id"] = sha256(canonical({k: v for k, v in normalized.items() if k != "contract_id"}))
    return normalized


def number(value: object, label: str, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        fail(f"{label} must be a finite number")
    result = float(value)
    if minimum is not None and result < minimum:
        fail(f"{label} must be >= {minimum}")
    return result


def stored_number(value: object, label: str, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        fail(f"{label} must be a stored finite number")
    if not math.isfinite(result):
        fail(f"{label} must be a stored finite number")
    if minimum is not None and result < minimum:
        fail(f"{label} must be >= {minimum}")
    return result


def rows(root: Path) -> list[dict[str, str]]:
    ledger = root / "experiments.tsv"
    if not ledger.exists():
        fail(f"missing ledger: {ledger}")
    with ledger.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != HEADER:
            fail("ledger header does not match schema")
        return list(reader)


def safe_field(value: object, label: str) -> str:
    text = str(value)
    if "\t" in text or "\n" in text or "\r" in text:
        fail(f"{label} cannot contain tabs or newlines")
    return text


def inside(root: Path, relative: object) -> str:
    value = safe_field(relative, "artifact")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.parts[:2] != ("measurements", "runs"):
        fail("artifact must be relative and live under measurements/runs")
    mission = root.resolve().parent
    resolved = (mission / path).resolve()
    if not resolved.is_relative_to(mission) or not resolved.is_file():
        fail(f"artifact does not exist inside mission root: {value}")
    if resolved.name != "artifact-manifest.json":
        fail("artifact must point to artifact-manifest.json")
    return value


def validate_manifest(root: Path, relative: str, contract: dict) -> set[str]:
    mission = root.resolve().parent
    manifest = load_json(mission / relative)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        fail("artifact manifest requires an artifacts list")
    external_roots = [
        Path(path).expanduser().resolve() for path in contract["output_paths"]
        if Path(path).expanduser().is_absolute()
    ]
    kinds = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            fail(f"artifact manifest item {index} must be an object")
        missing = {"kind", "path", "sha256", "size_bytes", "provenance"} - artifact.keys()
        if missing:
            fail(f"artifact manifest item {index} missing: {', '.join(sorted(missing))}")
        path = Path(artifact["path"]).expanduser() if isinstance(artifact["path"], str) else None
        if path is None:
            fail(f"artifact manifest item {index} path must be a string")
        kind = artifact["kind"]
        if not isinstance(kind, str) or not kind:
            fail(f"artifact manifest item {index} kind must be non-empty")
        kinds.add(kind)
        resolved = path.resolve() if path.is_absolute() else (mission / path).resolve()
        allowed = resolved.is_relative_to(mission) or any(resolved.is_relative_to(base) for base in external_roots)
        if not allowed or not resolved.is_file():
            fail(f"artifact manifest item {index} path is missing or outside configured roots")
        size = artifact["size_bytes"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0 or resolved.stat().st_size != size:
            fail(f"artifact manifest item {index} size_bytes does not match")
        if not isinstance(artifact["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
            fail(f"artifact manifest item {index} sha256 must be lowercase hexadecimal")
        if file_sha256(resolved) != artifact["sha256"]:
            fail(f"artifact manifest item {index} sha256 does not match")
        if not isinstance(artifact["provenance"], str) or not artifact["provenance"].strip():
            fail(f"artifact manifest item {index} provenance must be non-empty")
    return kinds


def improvement(candidate: float, reference: float, direction: str) -> float:
    return candidate - reference if direction == "maximize" else reference - candidate


def decide(contract: dict, result: dict, previous: dict[str, str] | None) -> tuple[str, str, str, float]:
    if result["iteration"] == 0:
        if previous is not None:
            fail("baseline must be the first row")
        if result["status"] != "valid" or any(
            result["gates"].get(gate) is not True for gate in contract["hard_gates"]
        ):
            fail("baseline must be valid and pass every hard gate")
        return "baseline", "baseline", "baseline", 0.0
    if previous is None:
        fail("candidate requires a baseline")
    status = result["status"]
    if status != "valid":
        return "discard", f"status:{status}", "invalid", 0.0
    gates = result["gates"]
    failed = [gate for gate in contract["hard_gates"] if gates.get(gate) is not True]
    if failed:
        return "discard", f"failed_gates:{','.join(failed)}", "invalid", 0.0
    primary = contract["primary"]
    value = number(result["metrics"].get(primary["name"]), f"metrics.{primary['name']}")
    reference = stored_number(previous["primary_value"], "reference primary")
    delta = improvement(value, reference, primary["direction"])
    tolerance = float(primary["tolerance"])
    if delta > tolerance:
        relation = "improved"
    elif delta < -tolerance:
        relation = "regressed"
    else:
        relation = "tied"
    previous_metrics = json.loads(previous["secondary_json"])
    for metric in contract["secondary"]:
        name = metric["name"]
        candidate_value = number(result["metrics"].get(name), f"metrics.{name}")
        reference_value = stored_number(previous_metrics.get(name), f"reference.{name}")
        secondary_delta = improvement(candidate_value, reference_value, metric["direction"])
        if secondary_delta < -float(metric.get("allowed_regression", 0)):
            return "discard", f"disallowed_regression:{name}", relation, delta
    if relation == "improved":
        return "keep", "primary_improved", relation, delta
    if relation == "regressed":
        return "discard", "primary_regressed", relation, delta
    for metric in contract["secondary"]:
        name = metric["name"]
        secondary_delta = improvement(
            number(result["metrics"].get(name), f"metrics.{name}"),
            stored_number(previous_metrics.get(name), f"reference.{name}"),
            metric["direction"],
        )
        if secondary_delta > float(metric.get("tolerance", 0)):
            return "keep", f"secondary_improved:{name}", relation, delta
        if secondary_delta < -float(metric.get("tolerance", 0)):
            return "discard", f"secondary_not_equivalent:{name}", relation, delta
    return "discard", "tie", relation, delta


def command_init(args: argparse.Namespace) -> None:
    root = measurement_root(args.mission_root)
    contract = validate_contract(load_json(args.contract))
    contract_path = root / "contract.json"
    if contract_path.exists() and load_json(contract_path) != contract:
        fail("measurement series already has a different contract")
    root.mkdir(parents=True, exist_ok=True)
    atomic_write(contract_path, json.dumps(contract, indent=2, sort_keys=True) + "\n")
    ledger = root / "experiments.tsv"
    if not ledger.exists():
        atomic_write(ledger, "\t".join(HEADER) + "\n")
    print(contract["contract_id"])


def command_append(args: argparse.Namespace) -> None:
    root = measurement_root(args.mission_root)
    contract = validate_contract(load_json(root / "contract.json"))
    result = load_json(args.result)
    existing = validate_rows(root, contract)
    missing = sorted(REQUIRED_RESULT - result.keys())
    if missing:
        fail(f"result missing fields: {', '.join(missing)}")
    if result["contract_id"] != contract["contract_id"]:
        fail("result contract_id is stale or incorrect")
    if result["evaluator_fingerprint"] != contract["evaluator"]["fingerprint"]:
        fail("result evaluator fingerprint does not match contract")
    iteration = result["iteration"]
    if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration != len(existing):
        fail(f"iteration must be {len(existing)}")
    if result["status"] not in {"valid", "invalid", "crash"}:
        fail("status must be valid, invalid, or crash")
    if not isinstance(result["metrics"], dict) or not isinstance(result["gates"], dict):
        fail("metrics and gates must be objects")
    unexpected_gates = set(result["gates"]) - set(contract["hard_gates"])
    if unexpected_gates or any(not isinstance(value, bool) for value in result["gates"].values()):
        fail("gates must contain only declared boolean gates")
    if result["status"] == "valid" and set(result["gates"]) != set(contract["hard_gates"]):
        fail("valid result must report every hard gate")
    runtime = number(result["runtime_s"], "runtime_s", minimum=0)
    memory = "NA" if result["peak_memory_mb"] is None else number(result["peak_memory_mb"], "peak_memory_mb", minimum=0)
    loc = result["non_test_loc"]
    if isinstance(loc, bool) or not isinstance(loc, int):
        fail("non_test_loc must be an integer")
    primary_name = contract["primary"]["name"]
    primary_value = "NA"
    if result["status"] == "valid":
        primary_value = number(result["metrics"].get(primary_name), f"metrics.{primary_name}")
    secondary = {}
    if result["status"] == "valid":
        secondary = {metric["name"]: number(result["metrics"].get(metric["name"]), f"metrics.{metric['name']}") for metric in contract["secondary"]}
    incumbent = next((row for row in reversed(existing) if row["decision"] in {"baseline", "keep"}), None)
    decision, reason, relation, delta = decide(contract, result, incumbent)
    artifact = inside(root, result["artifact"])
    kinds = validate_manifest(root, artifact, contract)
    required_kinds = {"ownership_snapshot"}
    if iteration:
        required_kinds.add("candidate_patch")
    if not required_kinds <= kinds:
        fail(f"artifact manifest missing kinds: {', '.join(sorted(required_kinds - kinds))}")
    row = {
        "schema": SCHEMA,
        "contract_id": contract["contract_id"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "iteration": iteration,
        "candidate": safe_field(result["candidate"], "candidate"),
        "revision": safe_field(result["revision"], "revision"),
        "hypothesis": safe_field(result["hypothesis"], "hypothesis"),
        "reference_revision": "NA" if incumbent is None else incumbent["revision"],
        "primary_value": primary_value,
        "primary_delta": delta if result["status"] == "valid" else "NA",
        "primary_relation": relation,
        "secondary_json": canonical(secondary),
        "gate_json": canonical(result["gates"]),
        "runtime_s": runtime,
        "peak_memory_mb": memory,
        "non_test_loc": loc,
        "status": result["status"],
        "decision": decision,
        "decision_reason": reason,
        "artifact": artifact,
    }
    content = (root / "experiments.tsv").read_text()
    content += "\t".join(safe_field(row[name], name) for name in HEADER) + "\n"
    atomic_write(root / "experiments.tsv", content)
    print(f"{decision}\t{reason}")


def validate_rows(root: Path, contract: dict) -> list[dict[str, str]]:
    ledger_rows = rows(root)
    incumbent = None
    for index, row in enumerate(ledger_rows):
        if row["schema"] != SCHEMA or row["contract_id"] != contract["contract_id"]:
            fail(f"row {index} has stale schema or contract")
        if int(row["iteration"]) != index:
            fail(f"row {index} is out of order")
        if row["status"] not in {"valid", "invalid", "crash"}:
            fail(f"row {index} has invalid status")
        if any(not row[field] for field in ("candidate", "revision", "hypothesis")):
            fail(f"row {index} has empty identity fields")
        if row["decision"] not in {"baseline", "keep", "discard"}:
            fail(f"row {index} has invalid decision")
        if row["primary_relation"] not in {"baseline", "improved", "regressed", "tied", "invalid"}:
            fail(f"row {index} has invalid primary relation")
        try:
            timestamp = datetime.fromisoformat(row["timestamp_utc"])
        except ValueError:
            fail(f"row {index} has invalid timestamp")
        if timestamp.tzinfo is None:
            fail(f"row {index} timestamp must include a timezone")
        stored_number(row["runtime_s"], f"row {index} runtime_s", minimum=0)
        if row["peak_memory_mb"] != "NA":
            stored_number(row["peak_memory_mb"], f"row {index} peak_memory_mb", minimum=0)
        try:
            int(row["non_test_loc"])
        except ValueError:
            fail(f"row {index} non_test_loc must be an integer")
        secondary = json.loads(row["secondary_json"])
        gates = json.loads(row["gate_json"])
        if not isinstance(secondary, dict) or not isinstance(gates, dict):
            fail(f"row {index} metrics and gates must be objects")
        if set(gates) - set(contract["hard_gates"]) or any(not isinstance(value, bool) for value in gates.values()):
            fail(f"row {index} has undeclared or non-boolean gates")
        expected_secondary = {metric["name"] for metric in contract["secondary"]}
        if row["status"] == "valid":
            if set(gates) != set(contract["hard_gates"]) or set(secondary) != expected_secondary or row["primary_value"] == "NA":
                fail(f"row {index} valid result is incomplete")
        elif secondary or row["primary_value"] != "NA" or row["primary_delta"] != "NA":
            fail(f"row {index} invalid result contains measured values")
        artifact = inside(root, row["artifact"])
        kinds = validate_manifest(root, artifact, contract)
        required_kinds = {"ownership_snapshot"}
        if index:
            required_kinds |= {"candidate_patch", "restore_proof"}
        if not required_kinds <= kinds:
            fail(f"row {index} artifact manifest missing kinds: {', '.join(sorted(required_kinds - kinds))}")
        expected_reference = "NA" if incumbent is None else incumbent["revision"]
        if row["reference_revision"] != expected_reference:
            fail(f"row {index} references the wrong incumbent")
        metrics = dict(secondary)
        if row["primary_value"] != "NA":
            metrics[contract["primary"]["name"]] = float(row["primary_value"])
        expected = decide(contract, {
            "iteration": index, "status": row["status"], "gates": gates,
            "metrics": metrics,
        }, incumbent)
        decision, reason, relation, delta = expected
        if (row["decision"], row["decision_reason"], row["primary_relation"]) != (decision, reason, relation):
            fail(f"row {index} decision does not follow the contract")
        if row["primary_delta"] != "NA" and not math.isclose(float(row["primary_delta"]), delta):
            fail(f"row {index} primary delta does not follow the contract")
        if decision in {"baseline", "keep"}:
            incumbent = row
    if ledger_rows and ledger_rows[0]["decision"] != "baseline":
        fail("first row must be the baseline")
    return ledger_rows


def command_validate(args: argparse.Namespace) -> None:
    root = measurement_root(args.mission_root)
    contract = validate_contract(load_json(root / "contract.json"))
    ledger_rows = validate_rows(root, contract)
    print(f"ok: {len(ledger_rows)} rows; contract {contract['contract_id']}")


def svg_report(ledger_rows: list[dict[str, str]], metric: str) -> str:
    valid = [(int(row["iteration"]), float(row["primary_value"]), row["decision"]) for row in ledger_rows if row["primary_value"] != "NA"]
    width, height, pad = 760, 360, 54
    if not valid:
        points = []
        low, high = 0.0, 1.0
    else:
        values = [value for _, value, _ in valid]
        low, high = min(values), max(values)
        if low == high:
            low, high = low - 0.5, high + 0.5
        points = [
            (pad + (width - 2 * pad) * iteration / max(1, len(ledger_rows) - 1),
             height - pad - (height - 2 * pad) * (value - low) / (high - low), decision)
            for iteration, value, decision in valid
        ]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{("#18864b" if decision in {"keep", "baseline"} else "#c43c35")}"/>'
        for x, y, decision in points
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/><text x="{pad}" y="28" font-family="sans-serif" font-size="18">{html.escape(metric)} by experiment</text>
<line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#555"/><line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#555"/>
<text x="8" y="{pad}" font-family="sans-serif" font-size="11">{high:.6g}</text><text x="8" y="{height-pad}" font-family="sans-serif" font-size="11">{low:.6g}</text>
<polyline points="{polyline}" fill="none" stroke="#2463a8" stroke-width="2"/>{circles}
<text x="{width/2-35}" y="{height-12}" font-family="sans-serif" font-size="12">iteration</text>
<text x="{width-210}" y="28" font-family="sans-serif" font-size="11" fill="#18864b">● kept</text><text x="{width-140}" y="28" font-family="sans-serif" font-size="11" fill="#c43c35">● discarded</text>
</svg>\n'''


def command_report(args: argparse.Namespace) -> None:
    root = measurement_root(args.mission_root)
    contract = validate_contract(load_json(root / "contract.json"))
    ledger_rows = validate_rows(root, contract)
    decisions = {name: sum(row["decision"] == name for row in ledger_rows) for name in ("baseline", "keep", "discard")}
    trailing = 0
    for row in reversed(ledger_rows):
        if row["decision"] == "discard":
            trailing += 1
        else:
            break
    summary = {
        "schema_version": int(SCHEMA),
        "contract_id": contract["contract_id"],
        "primary_metric": contract["primary"],
        "rows": len(ledger_rows),
        "decisions": decisions,
        "plateau": trailing >= 3,
        "trailing_non_improvements": trailing,
        "latest_revision": ledger_rows[-1]["revision"] if ledger_rows else None,
    }
    atomic_write(root / "summary.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    markdown = [
        "# Experiment summary", "", f"- Contract: `{contract['contract_id']}`",
        f"- Rows: {len(ledger_rows)}", f"- Kept: {decisions['keep']}",
        f"- Discarded: {decisions['discard']}", f"- Plateau: {'yes' if summary['plateau'] else 'no'}", "",
        "See `experiments.tsv` for the complete append-only ledger and `progress.svg` for the primary metric.", "",
    ]
    atomic_write(root / "summary.md", "\n".join(markdown))
    atomic_write(root / "progress.svg", svg_report(ledger_rows, contract["primary"]["name"]))
    print(root / "summary.json")


EXAMPLE_CONTRACT = {
    "evaluator": {"command": "python3 evaluate.py", "fingerprint": "sha256:replace-me"},
    "data": "dataset/split@version", "hard_gates": ["tests"],
    "primary": {"name": "loss", "direction": "minimize", "tolerance": 0.001},
    "secondary": [{"name": "runtime_s", "direction": "minimize", "tolerance": 0.01, "allowed_regression": 0.1}],
    "mutable_paths": ["src/model.py"], "budget": {"steps": 100}, "device": "mps",
    "seed": 42, "output_paths": ["artifacts/"], "rollback": "reverse candidate patch",
}
EXAMPLE_RESULT = {
    "contract_id": "copy from init", "evaluator_fingerprint": "sha256:replace-me",
    "iteration": 0, "candidate": "baseline", "revision": "git-or-content-hash",
    "hypothesis": "baseline", "metrics": {"loss": 1.0, "runtime_s": 10.0},
    "gates": {"tests": True}, "runtime_s": 10.0, "peak_memory_mb": None,
    "non_test_loc": 0, "status": "valid",
    "artifact": "measurements/runs/0000-baseline/artifact-manifest.json",
}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="validate and freeze a contract")
    init.add_argument("--mission-root", type=Path, required=True)
    init.add_argument("--contract", type=Path, required=True)
    init.set_defaults(run=command_init)
    append = commands.add_parser("append", help="validate and append one evaluator result")
    append.add_argument("--mission-root", type=Path, required=True)
    append.add_argument("--result", type=Path, required=True)
    append.set_defaults(run=command_append)
    validate = commands.add_parser("validate", help="validate contract, ledger, and artifact paths")
    validate.add_argument("--mission-root", type=Path, required=True)
    validate.set_defaults(run=command_validate)
    report = commands.add_parser("report", help="write JSON, Markdown, and SVG progress reports")
    report.add_argument("--mission-root", type=Path, required=True)
    report.set_defaults(run=command_report)
    commands.add_parser("example-contract", help="print an example contract").set_defaults(run=lambda _: print(json.dumps(EXAMPLE_CONTRACT, indent=2)))
    commands.add_parser("example-result", help="print an example result").set_defaults(run=lambda _: print(json.dumps(EXAMPLE_RESULT, indent=2)))
    return result


if __name__ == "__main__":
    arguments = parser().parse_args()
    arguments.run(arguments)
