"""Validate immutable performance evidence and mirror it to OMX and W&B."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .configs.wandb_config import WandbConfig

_CHECKPOINT_STATUSES = frozenset({"pass", "fail", "blocked"})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_REQUIRED_FIELDS = frozenset(
    {
        "schema_version",
        "goal_slug",
        "iteration",
        "title",
        "checkpoint_status",
        "summary",
        "hypothesis",
        "baseline_revision",
        "candidate_revision",
        "evaluator_fingerprint",
        "research",
        "metrics",
        "hard_gates",
        "series_axis",
    }
)


class ResultContractError(ValueError):
    """Raised when a result file cannot serve as immutable evaluator evidence."""


@dataclass(frozen=True)
class WandbPublication:
    """Verified W&B identity for one immutable SENPAI result."""

    run_id: str
    run_path: str


def load_result(path: Path) -> dict[str, Any]:
    """Load a version-two evaluator result for callers that need only its fields."""
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
    if raw["schema_version"] != 2:
        raise ResultContractError("result.schema_version must be 2")
    if isinstance(raw["iteration"], bool) or not isinstance(raw["iteration"], int) or raw["iteration"] <= 0:
        raise ResultContractError("result.iteration must be a positive integer")
    for field in (
        "goal_slug",
        "title",
        "summary",
        "hypothesis",
        "baseline_revision",
        "candidate_revision",
        "evaluator_fingerprint",
        "series_axis",
    ):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ResultContractError(f"result.{field} must be a non-empty string")
    if raw["checkpoint_status"] not in _CHECKPOINT_STATUSES:
        raise ResultContractError("result.checkpoint_status must be pass, fail, or blocked")
    _validate_research(raw["research"])
    _validate_scalar_mapping(raw["metrics"], field="metrics", boolean=False)
    _validate_scalar_mapping(raw["hard_gates"], field="hard_gates", boolean=True)
    if not raw["metrics"]:
        raise ResultContractError("result.metrics must not be empty")
    if not raw["hard_gates"]:
        raise ResultContractError("result.hard_gates must not be empty")
    _validate_evidence_series(raw.get("evidence_series", []))
    if raw["checkpoint_status"] == "pass" and not all(raw["hard_gates"].values()):
        raise ResultContractError("result.checkpoint_status cannot be pass when a hard gate failed")
    return raw, result_bytes


def _validate_research(value: Any) -> None:
    """Require one source-grounded research brief and approved assignment."""
    if not isinstance(value, Mapping):
        raise ResultContractError("result.research must be an object")
    for digest_field in ("brief_sha256", "assignment_sha256"):
        digest = value.get(digest_field)
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise ResultContractError(f"result.research.{digest_field} must be a lowercase SHA-256 digest")
    sources = value.get("sources")
    if not isinstance(sources, list):
        raise ResultContractError("result.research.sources must be a list")
    if not sources:
        raise ResultContractError("result.research.sources must not be empty")
    identities: set[tuple[str, str, str]] = set()
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping):
            raise ResultContractError(f"result.research.sources[{index}] must be an object")
        values: list[str] = []
        for field in ("kind", "locator", "version", "mechanism"):
            item = source.get(field)
            if not isinstance(item, str) or not item.strip():
                raise ResultContractError(f"result.research.sources[{index}].{field} must be a non-empty string")
            values.append(item.strip())
        identity = (values[0], values[1], values[2])
        if identity in identities:
            raise ResultContractError("result.research.sources must not contain duplicate identities")
        identities.add(identity)


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
    metric_keys: frozenset[str] | None = None
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
        point_metric_keys = frozenset(metrics)
        if metric_keys is not None and point_metric_keys != metric_keys:
            raise ResultContractError("result.evidence_series points must use the same metric keys")
        metric_keys = point_metric_keys
        previous_step = step


def result_sha256(result_bytes: bytes) -> str:
    """Return the digest of the exact evaluator bytes that were validated."""
    return hashlib.sha256(result_bytes).hexdigest()


def checkpoint_evidence(result: Mapping[str, Any], digest: str) -> str:
    """Build the concise, digest-backed evidence required by OMX checkpointing."""
    gates = sum(bool(value) for value in result["hard_gates"].values())
    total_gates = len(result["hard_gates"])
    return (
        f"result_sha256={digest}; iteration={result['iteration']}; candidate={result['candidate_revision']}; "
        f"baseline={result['baseline_revision']}; gates={gates}/{total_gates}; "
        f"summary={result['summary']}"
    )


def _wandb_provenance(result: Mapping[str, Any], digest: str) -> dict[str, Any]:
    research = result["research"]
    return {
        "goal_slug": result["goal_slug"],
        "iteration": result["iteration"],
        "checkpoint_status": result["checkpoint_status"],
        "hypothesis": result["hypothesis"],
        "baseline_revision": result["baseline_revision"],
        "candidate_revision": result["candidate_revision"],
        "evaluator_fingerprint": result["evaluator_fingerprint"],
        "research_brief_sha256": research["brief_sha256"],
        "assignment_sha256": research["assignment_sha256"],
        "research_source_count": len(research["sources"]),
        "result_sha256": digest,
    }


def _wandb_tags(result: Mapping[str, Any], configured: Sequence[str] | None) -> list[str]:
    required = (
        "senpai",
        f"goal:{result['goal_slug']}",
        f"iteration:{result['iteration']}",
        f"status:{result['checkpoint_status']}",
    )
    return list(dict.fromkeys((*configured, *required) if configured else required))


def _normalize_wandb_run_path(value: Any) -> tuple[str, str, str]:
    """Normalize W&B run paths across SDK tuple and slash-delimited forms."""
    components = value.split("/") if isinstance(value, str) else tuple(str(component) for component in value)
    if len(components) != 3 or not all(components):
        raise RuntimeError("W&B run path must contain entity, project, and run ID")
    return components[0], components[1], components[2]


def _verify_wandb_publication(
    wandb: Any,
    *,
    run_path: Sequence[str],
    result: Mapping[str, Any],
    digest: str,
) -> None:
    """Read back the published run identity and immutable-result provenance."""
    published = wandb.Api().run("/".join(run_path))
    expected_config = _wandb_provenance(result, digest)
    expected_tags = set(_wandb_tags(result, None))
    if published.name != f"[senpai] {result['title']}" or published.group != "senpai":
        raise RuntimeError("published W&B run does not have the required SENPAI identity")
    if not expected_tags.issubset(set(getattr(published, "tags", ()) or ())):
        raise RuntimeError("published W&B run does not have the required SENPAI tags")
    observed_config = published.config.get("aria_autoresearch", {})
    if observed_config != expected_config:
        raise RuntimeError("published W&B run does not preserve immutable evaluator provenance")


def log_wandb_result(
    result: Mapping[str, Any],
    result_bytes: bytes,
    digest: str,
    config: WandbConfig,
) -> WandbPublication:
    """Log a checkpointed result as a consistently named SENPAI observation."""
    import wandb

    init_kwargs = config.init_kwargs()
    init_kwargs["name"] = f"[senpai] {result['title']}"
    init_kwargs["group"] = "senpai"
    init_kwargs["tags"] = _wandb_tags(result, config.tags)
    run = wandb.init(
        **init_kwargs,
        config={"aria_autoresearch": _wandb_provenance(result, digest)},
    )
    run_id = str(run.id)
    run_path = _normalize_wandb_run_path(run.path)
    try:
        series = result.get("evidence_series", [])
        acquisition_number = f"aria_autoresearch/{result['series_axis']}"
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
            metadata={
                "result_sha256": digest,
                "checkpoint_status": result["checkpoint_status"],
                "iteration": result["iteration"],
                "hypothesis": result["hypothesis"],
                "research_brief_sha256": result["research"]["brief_sha256"],
                "assignment_sha256": result["research"]["assignment_sha256"],
            },
        )
        with artifact.new_file("result.json", mode="wb") as result_file:
            result_file.write(result_bytes)
        run.log_artifact(artifact)
    finally:
        run.finish()
    _verify_wandb_publication(wandb, run_path=run_path, result=result, digest=digest)
    return WandbPublication(run_id=run_id, run_path="/".join(run_path))


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
    if wandb_config is None:
        raise ResultContractError("formal SENPAI checkpoints require W&B configuration")
    pending_command = [
        "omx",
        "performance-goal",
        "checkpoint",
        "--slug",
        result["goal_slug"],
        "--status",
        "blocked",
        "--evidence",
        f"wandb_publication=pending; evaluator_status={result['checkpoint_status']}; {evidence}",
    ]
    pending = subprocess.run(
        pending_command,
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPOSITORY_ROOT,
    )
    publication = log_wandb_result(result, result_bytes, digest, wandb_config)
    command = [
        "omx",
        "performance-goal",
        "checkpoint",
        "--slug",
        result["goal_slug"],
        "--status",
        result["checkpoint_status"],
        "--evidence",
        f"wandb_run={publication.run_path}; {evidence}",
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=_REPOSITORY_ROOT,
    )
    outcome["omx_pending_stdout"] = pending.stdout
    outcome["omx_stdout"] = completed.stdout
    outcome["wandb_run_id"] = publication.run_id
    outcome["wandb_run_path"] = publication.run_path
    return outcome


def main(argv: Sequence[str] | None = None) -> int:
    """Run the immutable-result bridge as a small, explicit CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path, help="Immutable evaluator result.json")
    parser.add_argument("--wandb-project", default="aria-nbv", help="W&B project for the formal SENPAI run")
    parser.add_argument("--wandb-entity")
    parser.add_argument("--dry-run", action="store_true", help="Validate without W&B or OMX side effects")
    args = parser.parse_args(argv)
    config = WandbConfig(
        project=args.wandb_project,
        entity=args.wandb_entity,
        offline=False,
        job_type="performance-goal",
    )
    try:
        print(json.dumps(record_checkpoint(args.result, wandb_config=config, dry_run=args.dry_run), sort_keys=True))
    except ResultContractError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
