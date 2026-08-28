"""Generate one exact two-scene CUDA store for the target-orbit pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from aria_nbv.configs import PathConfig
from aria_nbv.oracle.pipelines.rollout_dataset import (
    RolloutDatasetWriterConfig,
    RolloutRecipeConfig,
)
from aria_nbv.pose_generation import (
    CandidateMixtureComponentConfig,
    CandidatePositionMode,
    ViewDirectionMode,
)
from aria_nbv.rollouts.replay.policy import (
    CounterfactualSelectionPolicy,
    RolloutPolicySpec,
)
from aria_nbv.rollouts.shard_manifest import (
    build_rollout_split_manifest_hash,
    read_rollout_source_manifest,
)

REPO = Path(__file__).resolve().parents[4]
WRITER_CONFIG = REPO / ".configs/build_rollouts_v1_cuda_campaign_writer.toml"
SOURCE_MANIFEST = REPO / ".configs/rollout_campaign100_source_manifest.json"


def _components(
    profile: str, config: RolloutDatasetWriterConfig
) -> list[CandidateMixtureComponentConfig]:
    current = {
        component.name: component for component in config.candidate_mixture.components
    }
    if profile == "realistic_core":
        return [
            current["forward_local"],
            current["target_bearing_local"],
            current["lateral_target_bypass"],
        ]
    return [
        current["forward_local"],
        current["target_bearing_local"].model_copy(update={"count": 12}),
        CandidateMixtureComponentConfig(
            name="target_orbit",
            count=12,
            view_mode=ViewDirectionMode.TARGET_POINT,
            position_mode=CandidatePositionMode.TARGET_ORBIT,
        ),
        current["lateral_target_bypass"],
    ]


def _resolved_config(
    profile: str,
    output_store: Path,
    *,
    data_root: Path,
    samples: int,
    seed: int,
) -> RolloutDatasetWriterConfig:
    PathConfig(root=REPO, data_root=data_root, offline_cache_dir=Path("offline_cache"))
    config = RolloutDatasetWriterConfig.from_toml(WRITER_CONFIG)
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    sample_keys = [str(row["sample_key"]) for row in manifest["rows"][:samples]]
    source_manifest = read_rollout_source_manifest(SOURCE_MANIFEST)
    rows_by_key = {row.sample_key: row for row in source_manifest.rows}
    selected_rows = [rows_by_key[sample_key] for sample_key in sample_keys]
    split_hash = build_rollout_split_manifest_hash(
        source_manifest_hash=source_manifest.source_manifest_hash,
        split=source_manifest.split,
        records=[
            {**row.hash_record(), "order": order}
            for order, row in enumerate(selected_rows)
        ],
    )
    mixture = config.candidate_mixture.model_copy(
        update={
            "base": config.candidate_mixture.base.model_copy(update={"seed": seed}),
            "components": _components(profile, config),
        }
    )
    recipe = RolloutRecipeConfig(
        name="temperature_softmax_h1",
        policy=RolloutPolicySpec(
            selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
            horizon=1,
            branch_factor=1,
            beam_width=1,
            selection_temperature=1.0,
            seed=seed,
        ),
    )
    return config.model_copy(
        update={
            "source": config.source.model_copy(
                update={"map_location": "cuda", "limit": int(manifest["num_rows"])}
            ),
            "source_manifest_path": SOURCE_MANIFEST,
            "sample_keys": sample_keys,
            "candidate_mixture": mixture,
            "recipes": [recipe],
            "max_samples": samples,
            "max_targets_per_sample": 1,
            "selected_depth": config.selected_depth.model_copy(
                update={"enabled": False}
            ),
            "store": config.store.model_copy(
                update={"store_dir": output_store, "split_manifest_hash": split_hash}
            ),
            "log_timing": True,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile", choices=("realistic_core", "target_orbit_mvp"), required=True
    )
    parser.add_argument("--output-store", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=REPO / ".data")
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260728)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("the pilot generation contract requires CUDA")
    output_store = args.output_store.expanduser().resolve()
    if output_store.exists():
        raise FileExistsError(f"refusing to overwrite existing store: {output_store}")
    result = (
        _resolved_config(
            args.profile,
            output_store,
            data_root=args.data_root.expanduser().resolve(),
            samples=args.samples,
            seed=args.seed,
        )
        .setup_target()
        .run()
    )
    print(
        json.dumps(
            {"store": str(result.store_dir), "manifest": str(result.manifest_path)},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
