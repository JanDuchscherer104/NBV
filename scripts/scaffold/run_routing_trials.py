#!/usr/bin/env python3
"""Run bounded, read-only Codex routing trials against an exact Git head."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_PATH = ROOT / "scripts" / "scaffold" / "fixtures" / "routing_prompts.jsonl"
RUBRIC_PATH = ROOT / "scripts" / "scaffold" / "fixtures" / "routing.json"
REPORT_SCHEMA = (
    ROOT / "scripts" / "scaffold" / "fixtures" / "routing_trial_report.schema.json"
)
DEFAULT_TRIAL_IDS = (
    "context7-graphify-api-change",
    "local-file-lookup",
    "context7-not-needed-target-rri-section",
    "package-contract-owner",
    "semantic-recall-reviewed-history",
    "concrete-failure",
    "durable-workpackage-completion",
    "oracle-evidence-construction",
    "oracle-private-scoring",
    "oracle-scene-rri-scoring",
    "oracle-target-rri-scoring",
    "oracle-label-dtos",
    "oracle-label-pipeline",
    "geometry-pose-generation",
    "geometry-rendering-camera",
    "geometry-vin-frame-contract",
    "zarr-rollout-storage-api",
    "zarr-offline-vin-storage-api",
)


def run_git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def load_prompts(path: Path = PROMPTS_PATH) -> dict[str, str]:
    prompts: dict[str, str] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        record = json.loads(line)
        if not isinstance(record, dict) or set(record) != {"id", "task"}:
            raise ValueError(f"{path}:{line_number}: expected only id and task")
        prompt_id = record["id"]
        task = record["task"]
        if not isinstance(prompt_id, str) or not isinstance(task, str):
            raise ValueError(f"{path}:{line_number}: id and task must be strings")
        if prompt_id in prompts:
            raise ValueError(f"{path}:{line_number}: duplicate id {prompt_id!r}")
        prompts[prompt_id] = task
    return prompts


def load_rubric_ids(path: Path = RUBRIC_PATH) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError(f"{path}: fixtures must be a list")
    ids = [fixture.get("id") for fixture in fixtures if isinstance(fixture, dict)]
    if not all(isinstance(fixture_id, str) for fixture_id in ids):
        raise ValueError(f"{path}: every fixture needs a string id")
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate fixture id")
    return set(ids)


def build_codex_command(
    *,
    checkout: Path,
    model_report: Path,
    model: str | None,
    effort: str | None,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--json",
        "--output-schema",
        str(REPORT_SCHEMA),
        "--output-last-message",
        str(model_report),
        "-C",
        str(checkout),
        "-c",
        'approval_policy="never"',
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("-")
    return command


def _find_named_values(value: Any, names: set[str]) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in names:
                found.append(child)
            found.extend(_find_named_values(child, names))
    elif isinstance(value, list):
        for child in value:
            found.extend(_find_named_values(child, names))
    return found


def read_event_summary(path: Path) -> dict[str, Any]:
    event_types: list[str] = []
    observed_models: list[Any] = []
    observed_usage: list[Any] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and isinstance(event.get("type"), str):
            event_types.append(event["type"])
        observed_models.extend(_find_named_values(event, {"model"}))
        observed_usage.extend(
            _find_named_values(event, {"usage", "token_usage", "context_usage"})
        )
    return {
        "event_types": sorted(set(event_types)),
        "observed_models": observed_models,
        "observed_usage": observed_usage,
    }


def run_trial(
    *,
    trial_id: str,
    task: str,
    head: str,
    checkout: Path,
    output_dir: Path,
    codex_version: str,
    model: str | None,
    effort: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    trial_dir = output_dir / trial_id
    trial_dir.mkdir(parents=True, exist_ok=False)
    events_path = trial_dir / "events.jsonl"
    stderr_path = trial_dir / "stderr.txt"
    model_report = trial_dir / "model-report.json"
    final_report = trial_dir / "report.json"
    command = build_codex_command(
        checkout=checkout,
        model_report=model_report,
        model=model,
        effort=effort,
    )
    clean_before = run_git("status", "--porcelain", cwd=checkout)
    started = time.time()
    with (
        events_path.open("w", encoding="utf-8") as events,
        stderr_path.open("w", encoding="utf-8") as stderr,
    ):
        try:
            result = subprocess.run(
                command,
                input=task,
                cwd=ROOT,
                stdout=events,
                stderr=stderr,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=os.environ.copy(),
            )
            returncode = result.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            returncode = 124
            timed_out = True
    clean_after = run_git("status", "--porcelain", cwd=checkout)
    runtime = {
        "codex_version": codex_version,
        "requested_model": model,
        "requested_effort": effort,
        "command_flags": command[1:-1],
        **read_event_summary(events_path),
    }
    model_payload: Any = None
    if model_report.is_file():
        try:
            model_payload = json.loads(model_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            model_payload = model_report.read_text(encoding="utf-8")
    report = {
        "trial_id": trial_id,
        "prompt_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "tested_commit": head,
        "runtime": runtime,
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "returncode": returncode,
        "timed_out": timed_out,
        "checkout_clean_before": clean_before == "",
        "checkout_clean_after": clean_after == "",
        "artifacts": {
            "events": events_path.name,
            "stderr": stderr_path.name,
            "model_report": model_report.name,
        },
        "model_report": model_payload,
    }
    final_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", default="HEAD", help="Exact commit-ish to test.")
    parser.add_argument(
        "--id", action="append", dest="ids", help="Trial ID; repeat to select several."
    )
    parser.add_argument("--all", action="store_true", help="Run every frozen prompt.")
    parser.add_argument("--list", action="store_true", help="List default trial IDs.")
    parser.add_argument(
        "--model", help="Explicit Codex model; otherwise inherit config."
    )
    parser.add_argument(
        "--effort", help="Explicit reasoning effort; otherwise inherit config."
    )
    parser.add_argument(
        "--jobs", type=int, default=1, help="Concurrent read-only trials."
    )
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per trial.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prompts = load_prompts()
    rubric_ids = load_rubric_ids()
    if set(prompts) != rubric_ids:
        raise SystemExit("routing prompt and rubric ID sets differ")
    selected = tuple(prompts) if args.all else tuple(args.ids or DEFAULT_TRIAL_IDS)
    unknown = sorted(set(selected) - set(prompts))
    if unknown:
        raise SystemExit(f"unknown trial IDs: {unknown}")
    if args.list:
        print("\n".join(selected))
        return 0
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    if run_git("status", "--porcelain"):
        raise SystemExit("commit the candidate before routing trials")

    head = run_git("rev-parse", args.head)
    short_head = head[:12]
    output_dir = ROOT / ".agents" / "work" / "routing-trials" / short_head
    if output_dir.exists():
        raise SystemExit(f"trial output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    codex_version = subprocess.run(
        ["codex", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory(prefix=f"aria-routing-{short_head}-") as temp:
        checkout = Path(temp) / "checkout"
        run_git("worktree", "add", "--detach", str(checkout), head)
        try:
            reports: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = {
                    executor.submit(
                        run_trial,
                        trial_id=trial_id,
                        task=prompts[trial_id],
                        head=head,
                        checkout=checkout,
                        output_dir=output_dir,
                        codex_version=codex_version,
                        model=args.model,
                        effort=args.effort,
                        timeout_seconds=args.timeout,
                    ): trial_id
                    for trial_id in selected
                }
                for future in as_completed(futures):
                    trial_id = futures[future]
                    report = future.result()
                    reports.append(report)
                    print(
                        f"{trial_id}: returncode={report['returncode']} "
                        f"clean={report['checkout_clean_after']}"
                    )
        finally:
            run_git("worktree", "remove", "--force", str(checkout))

    index = {
        "tested_commit": head,
        "codex_version": codex_version,
        "trial_ids": list(selected),
        "reports": [
            {
                "trial_id": report["trial_id"],
                "returncode": report["returncode"],
                "timed_out": report["timed_out"],
                "checkout_clean_after": report["checkout_clean_after"],
                "report": f"{report['trial_id']}/report.json",
            }
            for report in sorted(reports, key=lambda value: value["trial_id"])
        ],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return (
        0
        if all(
            report["returncode"] == 0 and report["checkout_clean_after"]
            for report in reports
        )
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
