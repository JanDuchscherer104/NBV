#!/usr/bin/env bash
#SBATCH --job-name=aria-rollout
#SBATCH --partition=lrz-v100x2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=02:00:00
#SBATCH --output=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%A_%a.out
#SBATCH --error=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%A_%a.err

set -euo pipefail

: "${ARIA_DSS:?Set ARIA_DSS to the DSS root for large ARIA-NBV artifacts.}"
: "${ARIA_REPO:?Set ARIA_REPO to the ARIA-NBV checkout on LRZ.}"
: "${LRZ_CONTAINER_IMAGE:?Set LRZ_CONTAINER_IMAGE to an Enroot/Pyxis image URI.}"
: "${RUN_ID:?Set RUN_ID to the rollout generation campaign id.}"
: "${CONFIG_PATH:?Set CONFIG_PATH to a rollout writer TOML with DSS-backed paths.}"
: "${SHARD_MANIFEST:?Set SHARD_MANIFEST to the JSONL emitted by nbv-plan-rollout-shards.}"

: "${SLURM_ARRAY_TASK_ID:?Submit with --array=0-(NUM_SHARDS-1).}"
ARRAY_TASK_ID="$SLURM_ARRAY_TASK_ID"
SHARD_ID="$(printf 'shard-%06d' "$ARRAY_TASK_ID")"
JOB_ID="${SLURM_JOB_ID:-manual}"
FINAL_SHARD_DIR="$ARIA_DSS/data/staging/rollouts/$RUN_ID/shards/$SHARD_ID"
TEMP_SHARD_DIR="$ARIA_DSS/tmp/$JOB_ID/rollouts/$RUN_ID/$SHARD_ID.tmp"

mkdir -p "$ARIA_DSS/logs/slurm" "$ARIA_DSS/tmp/$JOB_ID/rollouts/$RUN_ID"

export ARIA_DSS ARIA_REPO CONFIG_PATH SHARD_MANIFEST SHARD_ID FINAL_SHARD_DIR TEMP_SHARD_DIR

echo "ARIA-NBV rollout generation"
echo "  job_id=$JOB_ID"
echo "  array_task_id=$ARRAY_TASK_ID"
echo "  shard_id=$SHARD_ID"
echo "  config_path=$CONFIG_PATH"
echo "  shard_manifest=$SHARD_MANIFEST"
echo "  temp_shard_dir=$TEMP_SHARD_DIR"
echo "  final_shard_dir=$FINAL_SHARD_DIR"

srun --ntasks=1 \
  --container-image="$LRZ_CONTAINER_IMAGE" \
  --container-mounts="$HOME:$HOME,$ARIA_DSS:$ARIA_DSS,$ARIA_REPO:$ARIA_REPO" \
  bash -lc 'set -euo pipefail
cd "$ARIA_REPO"
source .agents/skills/lrz-ai-systems/scripts/lrz-aria-env.sh "$ARIA_DSS"
nvidia-smi
command -v uv >/dev/null
cd aria_nbv
test -x .venv/bin/python
uv run --frozen --no-sync nbv-build-rollouts \
  --config-path "$CONFIG_PATH" \
  --shard-manifest "$SHARD_MANIFEST" \
  --shard-id "$SHARD_ID" \
  --output-tmp "$TEMP_SHARD_DIR" \
  --output-final "$FINAL_SHARD_DIR"'
