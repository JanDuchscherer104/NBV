"""Validate immutable performance evidence and mirror it to OMX and W&B."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .configs.wandb_config import WandbConfig

_CHECKPOINT_STATUSES = frozenset({"pass", "fail", "blocked"})
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "goal_slug",
        "title",
        "checkpoint_status",
        "summary",
        "baseline_revision",
        "candidate_revision",
        "evaluator_fingerprint",
        "metrics",
        "hard_gates",
    }
)


class ResultContractError(ValueError):
    """Raised when a result file cannot serve as immutable evaluator evidence."""


def load_result(path: Path) -> dict[str, Any]:
    """Load a version-one evaluator result for callers that need only its fields."""
    result, _ = load_result_snapshot(path)
    return result


def load_result_snapshot(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read once, validate, and retain the exact evaluator-result bytes."""
    try:
        result_bytes = path.read_bytes()
        raw = json.loads(result_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ResultContractError(f"cannot read JSON result: {exc}") from exc
    if not isinstance(raw, dict):
        raise ResultContractError("result must be a JSON object")
    missing = sorted(_REQUIRED_FIELDS.difference(raw))
    if missing:
        raise ResultContractError(f"result is missing required fields: {', '.join(missing)}")
    if raw["schema_version"] != 1:
        raise ResultContractError("result.schema_version must be 1")
    for field in ("goal_slug", "title", "summary", "baseline_revision", "candidate_revision", "evaluator_fingerprint"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ResultContractError(f"result.{field} must be a non-empty string")
    if raw["checkpoint_status"] not in _CHECKPOINT_STATUSES:
        raise ResultContractError("result.checkpoint_status must be pass, fail, or blocked")
    _validate_scalar_mapping(raw["metrics"], field="metrics", boolean=False)
    _validate_scalar_mapping(raw["hard_gates"], field="hard_gates", boolean=True)
    _validate_evidence_series(raw.get("evidence_series", []))
    if raw["checkpoint_status"] == "pass" and not all(raw["hard_gates"].values()):
        raise ResultContractError("result.checkpoint_status cannot be pass when a hard gate failed")
    return raw, result_bytes


def _validate_scalar_mapping(value: Any, *, field: str, boolean: bool) -> None:
    if not isinstance(value, Mapping):
        raise ResultContractError(f"result.{field} must be an object")
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ResultContractError(f"result.{field} keys must be non-empty strings")
        if boolean:
            if not isinstance(item, bool):
                raise ResultContractError(f"result.{field}.{key} must be boolean")
        elif isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise ResultContractError(f"result.{field}.{key} must be a finite number")


def _validate_evidence_series(value: Any) -> None:
    """Require monotonic, finite evaluator measurements when a series is supplied."""
    if not isinstance(value, list):
        raise ResultContractError("result.evidence_series must be a list")
    previous_step = 0
    for index, point in enumerate(value):
        if not isinstance(point, Mapping):
            raise ResultContractError(f"result.evidence_series[{index}] must be an object")
        step = point.get("step")
        if isinstance(step, bool) or not isinstance(step, int) or step <= previous_step:
            raise ResultContractError("result.evidence_series steps must be strictly increasing positive integers")
        metrics = point.get("metrics")
        _validate_scalar_mapping(metrics, field=f"evidence_series[{index}].metrics", boolean=False)
        if not metrics:
            raise ResultContractError(f"result.evidence_series[{index}].metrics must not be empty")
        previous_step = step


def result_sha256(result_bytes: bytes) -> str:
    """Return the digest of the exact evaluator bytes that were validated."""
    return hashlib.sha256(result_bytes).hexdigest()


def checkpoint_evidence(result: Mapping[str, Any], digest: str) -> str:
    """Build the concise, digest-backed evidence required by OMX checkpointing."""
    gates = sum(bool(value) for value in result["hard_gates"].values())
    total_gates = len(result["hard_gates"])
    return (
        f"result_sha256={digest}; candidate={result['candidate_revision']}; "
        f"baseline={result['baseline_revision']}; gates={gates}/{total_gates}; "
        f"summary={result['summary']}"
    )


def log_wandb_result(result: Mapping[str, Any], result_bytes: bytes, digest: str, config: WandbConfig) -> str:
    """Log a checkpointed result as a consistently named SENPAI observation."""
    import wandb

    init_kwargs = config.init_kwargs()
    init_kwargs["name"] = f"[senpai] {result['title']}"
    init_kwargs["group"] = "senpai"
    run = wandb.init(
        **init_kwargs,
        config={
            "aria_autoresearch": {
                "goal_slug": result["goal_slug"],
                "checkpoint_status": result["checkpoint_status"],
                "baseline_revision": result["baseline_revision"],
                "candidate_revision": result["candidate_revision"],
                "evaluator_fingerprint": result["evaluator_fingerprint"],
                "result_sha256": digest,
            }
        },
    )
    try:
        series = result.get("evidence_series", [])
        acquisition_number = "aria_autoresearch/acquisition_number"
        run.define_metric(acquisition_number, hidden=True)
        for point in series:
            for key in point["metrics"]:
                run.define_metric(f"aria_autoresearch/{key}", step_metric=acquisition_number)
        for point in series:
            run.log(
                {
                    acquisition_number: point["step"],
                    **{f"aria_autoresearch/{key}": value for key, value in point["metrics"].items()},
                },
                step=point["step"],
            )
        run.summary.update({f"aria_autoresearch/{key}": value for key, value in result["metrics"].items()})
        artifact = wandb.Artifact(
            name=f"performance-goal-{result['goal_slug']}-{digest[:12]}",
            type="aria-performance-result",
            metadata={"result_sha256": digest, "checkpoint_status": result["checkpoint_status"]},
        )
        with artifact.new_file("result.json", mode="wb") as result_file:
            result_file.write(result_bytes)
        run.log_artifact(artifact)
        return str(run.id)
    finally:
        run.finish()


def record_checkpoint(
    result_path: Path,
    *,
    wandb_config: WandbConfig | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Validate, optionally mirror, then record one evaluator checkpoint with OMX."""
    resolved_path = result_path.resolve()
    result, result_bytes = load_result_snapshot(resolved_path)
    digest = result_sha256(result_bytes)
    evidence = checkpoint_evidence(result, digest)
    outcome: dict[str, Any] = {
        "result_path": resolved_path.as_posix(),
        "result_sha256": digest,
        "goal_slug": result["goal_slug"],
        "checkpoint_status": result["checkpoint_status"],
        "evidence": evidence,
    }
    if dry_run:
        outcome["dry_run"] = True
        return outcome
    command = [
        "omx",
        "performance-goal",
        "checkpoint",
        "--slug",
        result["goal_slug"],
        "--status",
        result["checkpoint_status"],
        "--evidence",
        evidence,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPOSITORY_ROOT,
    )
    outcome["omx_stdout"] = completed.stdout
    if wandb_config is not None:
        try:
            outcome["wandb_run_id"] = log_wandb_result(result, result_bytes, digest, wandb_config)
        except Exception as exc:  # W&B is an optional mirror, never the gate.
            outcome["wandb_error"] = str(exc)
    return outcome


def main(argv: Sequence[str] | None = None) -> int:
    """Run the immutable-result bridge as a small, explicit CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="Immutable evaluator result.json")
    parser.add_argument("--wandb-project", help="Mirror evidence to this W&B project")
    parser.add_argument("--wandb-entity")
    parser.add_argument("--wandb-offline", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate without W&B or OMX side effects")
    args = parser.parse_args(argv)
    config = None
    if args.wandb_project:
        config = WandbConfig(
            project=args.wandb_project,
            entity=args.wandb_entity,
            job_type="performance-goal",
            offline=args.wandb_offline,
        )
    try:
        print(json.dumps(record_checkpoint(args.result, wandb_config=config, dry_run=args.dry_run), sort_keys=True))
    except ResultContractError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
