#!/usr/bin/env bash
#SBATCH --job-name=aria-qh-train
#SBATCH --partition=lrz-hgx-h100-94x4
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=32
#SBATCH --mem=240G
#SBATCH --time=04:00:00
#SBATCH --output=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%j.out
#SBATCH --error=/ABS/PATH/TO/ARIA_DSS/logs/slurm/%x-%j.err

set -euo pipefail

ARIA_DSS="${ARIA_DSS:-/ABS/PATH/TO/ARIA_DSS}"
ARIA_REPO="${ARIA_REPO:-$HOME/src/ARIA-NBV}"
if [[ -z "${LRZ_CONTAINER_IMAGE:-}" ]] \
  || [[ -z "${LRZ_CONTAINER_IMAGE//[[:space:]]/}" ]]; then
  echo "LRZ_CONTAINER_IMAGE must be nonblank." >&2
  exit 2
fi
QH_CONFIG="${QH_CONFIG:-$ARIA_REPO/.configs/training/qh/train_qh_v0_lrz.template.toml}"
GPUS_ON_NODE="${SLURM_GPUS_ON_NODE:-}"

if [[ ! "$GPUS_ON_NODE" =~ ^[1-9][0-9]*$ ]]; then
  echo "SLURM_GPUS_ON_NODE must be a positive integer." >&2
  exit 2
fi
if [[ "$GPUS_ON_NODE" != "2" ]]; then
  echo "SLURM_GPUS_ON_NODE must equal trainer.devices=2 for this template." >&2
  exit 2
fi
if [[ "${SLURM_JOB_NUM_NODES:-1}" != "1" ]]; then
  echo "Q_H training supports exactly one LRZ node." >&2
  exit 2
fi
if [[ "$(grep -Ec '^#SBATCH --gres=gpu:2$' "$0")" != "1" ]]; then
  echo "Q_H launch contract requires exactly #SBATCH --gres=gpu:2." >&2
  exit 2
fi
if [[ "$(grep -Ec '^[[:space:]]*srun[[:space:]]' "$0")" != "1" ]]; then
  echo "Q_H launch contract requires exactly one srun invocation." >&2
  exit 2
fi
if [[ "$(grep -Ec '^[[:space:]]*(exec[[:space:]]+)?(uv[[:space:]]+run[[:space:]]+--frozen[[:space:]]+--no-sync[[:space:]]+)?torchrun[[:space:]]' "$0")" != "1" ]] \
  || ! grep -Eq '^[[:space:]]*exec[[:space:]]+uv[[:space:]]+run[[:space:]]+--frozen[[:space:]]+--no-sync[[:space:]]+torchrun[[:space:]]' "$0"; then
  echo "Q_H launch contract requires exactly one torchrun invocation." >&2
  exit 2
fi
if ! grep -Eq '^#SBATCH --nodes=1$' "$0" || ! grep -Eq '^#SBATCH --ntasks-per-node=1$' "$0"; then
  echo "Q_H launch contract requires one node and one launcher task per node." >&2
  exit 2
fi
if ! grep -Eq '^[[:space:]]+command -v uv >/dev/null' "$0" \
  || ! grep -Eq '^[[:space:]]+test -x \.venv/bin/python' "$0"; then
  echo "Q_H launch contract requires a prepared frozen uv environment." >&2
  exit 2
fi

export ARIA_DSS ARIA_REPO QH_CONFIG GPUS_ON_NODE LRZ_CONTAINER_IMAGE
export QH_CKPT_PATH="${QH_CKPT_PATH:-}"

# This template is a one-node throughput/smoke launcher. Scientific claims must
# use scene-disjoint validation/test corpora and a held-out evaluation config.
# Checkpoint and target-network sync cadences are bounded in the paired TOML;
# sync checkpoints to DSS through site-approved job epilogues, not per step.

srun --ntasks=1 --ntasks-per-node=1 \
  --container-image="$LRZ_CONTAINER_IMAGE" \
  --container-mounts="$HOME:$HOME,$ARIA_DSS:$ARIA_DSS,$ARIA_REPO:$ARIA_REPO" \
  bash -lc '
    set -euo pipefail
    cd "$ARIA_REPO"
    source .agents/skills/lrz-ai-systems/scripts/lrz-aria-env.sh "$ARIA_DSS"
    command -v uv >/dev/null
    cd aria_nbv
    test -x .venv/bin/python
    checkpoint_args=()
    if [[ -n "$QH_CKPT_PATH" ]]; then
      checkpoint_args=(--ckpt-path "$QH_CKPT_PATH")
    fi
    exec uv run --frozen --no-sync torchrun --standalone --nproc_per_node="$GPUS_ON_NODE" \
      --module aria_nbv.lightning.qh_cli \
      --config-path "$QH_CONFIG" "${checkpoint_args[@]}"
  '
