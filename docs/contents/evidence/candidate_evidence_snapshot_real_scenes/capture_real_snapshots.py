"""Capture canonical candidate snapshots from already-acquired rollout stores."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from aria_nbv.rollouts.candidate_evidence import candidate_evidence_snapshot_from_stored
from aria_nbv.rollouts.read_model import rollout_at, rollout_steps, target_rows
from aria_nbv.rollouts.zarr_store import RolloutZarrStoreReader


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "stores",
        nargs="+",
        type=Path,
        help="Already-acquired rollout Zarr store roots.",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Destination snapshot JSON path."
    )
    parser.add_argument(
        "--rollout-index", type=int, default=0, help="Physical rollout row per store."
    )
    parser.add_argument(
        "--step-index", type=int, default=0, help="Factual step index per rollout."
    )
    return parser


def main() -> None:
    """Capture one reader-free snapshot per store with source-manifest hashes."""

    args = _parser().parse_args()
    snapshots: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for store in args.stores:
        reader = RolloutZarrStoreReader(store)
        rollout = rollout_at(reader, args.rollout_index)
        steps = rollout_steps(reader, rollout)
        if args.step_index < 0 or args.step_index >= len(steps):
            raise ValueError(f"step {args.step_index} is unavailable in {store}")
        step = steps[args.step_index]
        previous_step = None if args.step_index == 0 else steps[args.step_index - 1]
        target = next(
            value
            for value in target_rows(reader)
            if value.target_row_id == rollout.target_row_id
        )
        snapshot = candidate_evidence_snapshot_from_stored(
            rollout,
            step,
            target,
            previous_step=previous_step,
        )
        manifest_bytes = (store / "manifest.json").read_bytes()
        sources.append(
            {
                "campaign": "cuda-rollouts-v1-pilot-corrected-v11",
                "shard": store.name,
                "scene": rollout.scene,
                "snippet": rollout.snippet,
                "rollout_row_id": rollout.rollout_row_id,
                "step_row_id": step.step_row_id,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            }
        )
        snapshots.append(asdict(snapshot))
    payload = {
        "schema_revision": "candidate-evidence-real-scene-bundle-v1",
        "sources": sources,
        "snapshots": snapshots,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


if __name__ == "__main__":
    main()
