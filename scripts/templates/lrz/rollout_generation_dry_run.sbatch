#!/usr/bin/env bash
#SBATCH --job-name=aria-rollout-dryrun
#SBATCH --partition=lrz-v100x2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=00:20:00
#SBATCH --array=0-0
#SBATCH --output=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%A_%a.out
#SBATCH --error=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%A_%a.err

set -euo pipefail

ARIA_DSS="${ARIA_DSS:-/ABS/PATH/TO/ARIA_DSS}"
ARIA_REPO="${ARIA_REPO:-$HOME/src/ARIA-NBV}"
LRZ_CONTAINER_IMAGE="${LRZ_CONTAINER_IMAGE:-nvcr.io#nvidia/pytorch:24.10-py3}"
RUN_ID="${RUN_ID:-rollout-dryrun-YYYYMMDD}"
DATASET_VERSION="${DATASET_VERSION:-ORACLE_CACHE_VERSION_PLACEHOLDER}"
CONFIG_PATH="${CONFIG_PATH:-$ARIA_REPO/.configs/generation/rollouts/smoke/build_rollouts_v1_smoke.toml}"
SHARD_MANIFEST="${SHARD_MANIFEST:-$ARIA_DSS/data/staging/manifests/rollout_shards.jsonl}"
ARRAY_TASK_ID="${SLURM_ARRAY_TASK_ID:-0}"
SHARD_ID="$(printf 'shard-%06d' "$ARRAY_TASK_ID")"
JOB_ID="${SLURM_JOB_ID:-manual}"
FINAL_SHARD_DIR="$ARIA_DSS/data/staging/rollouts/$RUN_ID/shards/$SHARD_ID"
TEMP_SHARD_DIR="$ARIA_DSS/tmp/$JOB_ID/rollouts/$RUN_ID/$SHARD_ID.tmp"

cat <<DRYRUN
ARIA-NBV LRZ rollout generation dry run
=======================================

This template does not generate rollout traces or Q_H data. It documents the
Slurm/Pyxis shape and expected DSS paths for a future rollout writer.

Slurm:
  job_id: $JOB_ID
  array_task_id: $ARRAY_TASK_ID
  shard_id: $SHARD_ID
  partition_hint: lrz-v100x2 for smoke, A100/H100 80GB class partitions for scale
  gpu_request: --gres=gpu:1

Enroot/Pyxis:
  image: $LRZ_CONTAINER_IMAGE
  container_mounts: $HOME:$HOME,$ARIA_DSS:$ARIA_DSS,$ARIA_REPO:$ARIA_REPO

DSS:
  oracle_or_dataset_version: $DATASET_VERSION
  config_path: $CONFIG_PATH
  shard_manifest: $SHARD_MANIFEST
  temp_shard_dir: $TEMP_SHARD_DIR
  final_shard_dir: $FINAL_SHARD_DIR
  completion_marker: $FINAL_SHARD_DIR/_SUCCESS.json
  owner_sidecar: $FINAL_SHARD_DIR/_owner.json

Dry-run Pyxis launch shape:
  srun --ntasks=1 \\
    --container-image="$LRZ_CONTAINER_IMAGE" \\
    --container-mounts="$HOME:$HOME,$ARIA_DSS:$ARIA_DSS,$ARIA_REPO:$ARIA_REPO" \\
    bash -lc 'cd "$ARIA_REPO/aria_nbv" && uv run nbv-build-rollouts \\
      --config-path "$CONFIG_PATH" \\
      --shard-manifest "$SHARD_MANIFEST" \\
      --shard-id "$SHARD_ID" \\
      --output-tmp "$TEMP_SHARD_DIR" \\
      --output-final "$FINAL_SHARD_DIR" \\
      --dry-run'

Resume and atomic-write expectations:
  - one array task owns this final rollout shard path
  - retain lineage in the shard owner sidecar and final manifest
  - skip only validated completed shards
  - write temp first, validate, rename, then write completion marker
DRYRUN
