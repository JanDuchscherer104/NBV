# LRZ DSS Dry-Run Layout

This directory documents the LRZ staging contract used by the dry-run Slurm
templates in `scripts/templates/lrz/`. These files are planning aids only. They
do not define a package storage schema and are not consumed by `aria_nbv`.
The full data-generation operator sequence lives in
`aria_nbv/aria_nbv/data_handling/README.md`; this file only owns LRZ/DSS
placement, Slurm/Pyxis, and campaign retry semantics.

## Required Operator Variables

Set these in the submission environment or replace the placeholders in a copied
template:

| Variable | Meaning |
| --- | --- |
| `ARIA_DSS` | DSS root for ARIA-NBV large artifacts. Must not point inside `$HOME`. |
| `ARIA_REPO` | Checkout path on LRZ, usually `$HOME/src/ARIA-NBV`. |
| `LRZ_CONTAINER_IMAGE` | Enroot/Pyxis image URI, for example `nvcr.io#nvidia/pytorch:24.10-py3`. |
| `RUN_ID` | Human-readable run ID used in staging, logs, checkpoints, and manifests. |
| `DATASET_VERSION` | Dataset/cache version or immutable store version being consumed. |
| `CONFIG_PATH` | Rollout writer TOML with explicit DSS-backed paths. Copy `.configs/build_rollouts_v1_realistic.toml` into an untracked run config, then override DSS paths and shard/sample counts there. |
| `SHARD_MANIFEST` | JSONL or table that maps Slurm array task IDs to deterministic shards. |

## DSS Staging Layout

The base DSS layout is still owned by the LRZ helper scripts. Use the staging
subdirectories below for dry-run planning and later real generation jobs after
the package writer contracts are implemented.

```text
$ARIA_DSS/
  data/raw/
    ase/
    atek/
  data/processed/
    <dataset_version>/
  data/staging/
    manifests/
      oracle_shards.jsonl
      rollout_shards.jsonl
      diagnostics_shards.jsonl
    rollouts/<run_id>/
      shards/
      _tmp/
      manifests/
  caches/oracle/
    staging/<run_id>/
      shards/
      _tmp/
      manifests/
  caches/vin/
    <offline_store_version>/
  checkpoints/
    vin/<run_id>/
  logs/
    slurm/
    diagnostics/<run_id>/
    wandb/
  containers/
  tmp/
    <slurm_job_id>/
  .cache/
    uv/
    pip/
    huggingface/
    torch/
```

Keep raw ASE/ATEK downloads, generated oracle shards, rollout staging, VIN
offline stores, checkpoints, logs, containers, and package/model caches under
`$ARIA_DSS`. Keep code, small config, SSH config, git config, and private
credentials under `$HOME`.

## Quota And Inode Expectations

- Inspect the current allocation with `dssusrinfo all` before any scale job.
- Record both byte quota and inode pressure in the run notes before submitting
  arrays. Quotas and inode limits are allocation-specific and should not be
  hard-coded in templates.
- Prefer tar shards, HDF5/Zarr-style chunked stores, WebDataset-style shards, or
  compact JSONL manifests over millions of loose files.
- Keep temporary extraction, package caches, and model caches under
  `$ARIA_DSS/tmp/` or `$ARIA_DSS/.cache/`.
- Treat DSS as staging for generated experiments. Preserve important manifests,
  source config, and final reports in git or another durable project record when
  they are small enough to version.

## Shard Ownership

- One Slurm array task owns exactly one final shard path.
- Use deterministic shard IDs, for example `shard-000123`, derived from
  `SLURM_ARRAY_TASK_ID` and `SHARD_MANIFEST`.
- No two jobs may write the same final path. Split retry jobs by shard ID rather
  than by broad scene globs.
- Each shard should record owner metadata in a sidecar such as `_owner.json`,
  including `run_id`, `job_id`, `array_task_id`, source dataset version, git
  commit, config hash, and template name.
- Final manifests should reference shard IDs and content hashes, not transient
  temp paths.

## Resume Contract

- A shard is resumable only after its final completion marker exists, for
  example `_SUCCESS.json`.
- Resume logic must skip completed shards, retry failed shards explicitly, and
  ignore or delete stale temp directories after operator review.
- Failed attempts should write `_FAILED.json` or an equivalent manifest entry
  outside the final completed shard path.
- Large reruns should start from a manifest filter of missing or failed shard
  IDs, not from a blind re-scan of the full DSS tree.
- For rollout campaigns, use `nbv-status-rollout-shards --shard-manifest
  "$SHARD_MANIFEST" --final-root "$ARIA_DSS/data/staging/rollouts/$RUN_ID/shards"
  --output-json "$ARIA_DSS/data/staging/rollouts/$RUN_ID/manifests/status.json"`
  to list succeeded, failed, incomplete, and missing shards.

## Atomic Write Contract

- Write heavy outputs to a temp directory under the same DSS filesystem, for
  example `$ARIA_DSS/tmp/$SLURM_JOB_ID/<workflow>/<run_id>/shard-000123.tmp`.
- Validate the temp artifact before promotion.
- Promote by renaming the complete temp shard into its final path on the same
  filesystem.
- Write completion markers last.
- Never update a final shard in place. If a writer cannot be atomic at the store
  level, write a new versioned shard and update the manifest after validation.

## Dry-Run Template Map

| Workflow | Template | Expected final root |
| --- | --- | --- |
| Oracle generation | `scripts/templates/lrz/oracle_generation_dry_run.sbatch` | `$ARIA_DSS/caches/oracle/staging/$RUN_ID/shards/` |
| Rollout generation | `scripts/templates/lrz/rollout_generation_dry_run.sbatch` | `$ARIA_DSS/data/staging/rollouts/$RUN_ID/shards/` |
| VIN training | `scripts/templates/lrz/vin_training_dry_run.sbatch` | `$ARIA_DSS/checkpoints/vin/$RUN_ID/` |
| Diagnostics | `scripts/templates/lrz/diagnostics_dry_run.sbatch` | `$ARIA_DSS/logs/diagnostics/$RUN_ID/` |

## Real Rollout Array Template

Use `scripts/templates/lrz/rollout_generation.sbatch` after a one-row local or
interactive LRZ smoke succeeds. The real template runs `nbv-build-rollouts`
inside Pyxis for one deterministic shard per array task and expects:

1. A copied, edited rollout config based on the canonical thesis-default
   `.configs/build_rollouts_v1_realistic.toml`; keep LRZ DSS paths and
   campaign-scale counts in the copied untracked run config.
2. A shard manifest planned with `nbv-plan-rollout-shards`.
3. An array range matching the manifest shard count.
4. `RUN_ID`, `CONFIG_PATH`, `SHARD_MANIFEST`, `ARIA_DSS`, `ARIA_REPO`, and
   `LRZ_CONTAINER_IMAGE` exported in the submission environment.

Copy the template before submitting and replace the `/ABS/PATH/TO/ARIA_DSS`
`#SBATCH --output` and `#SBATCH --error` placeholders with the concrete DSS log
directory. Slurm parses `#SBATCH` directives before the shell starts, so those
lines do not expand `$ARIA_DSS` or other shell variables.

Minimal LRZ rollout campaign flow:

```sh
export ARIA_DSS=/dss/.../aria-nbv
export ARIA_REPO=$HOME/src/ARIA-NBV
export LRZ_CONTAINER_IMAGE='nvcr.io#nvidia/pytorch:24.10-py3'
export RUN_ID=rollouts-v1-smoke-YYYYMMDD
export CONFIG_PATH="$ARIA_DSS/data/staging/rollouts/build_rollouts_${RUN_ID}.toml"
export SHARD_MANIFEST="$ARIA_DSS/data/staging/manifests/rollout_shards_${RUN_ID}.jsonl"

cp "$ARIA_REPO/.configs/build_rollouts_v1_realistic.toml" "$CONFIG_PATH"
# Edit "$CONFIG_PATH" so source/store paths point at DSS artifacts and the
# sample/shard counts match the intended LRZ campaign.

cd "$ARIA_REPO/aria_nbv"
uv run nbv-plan-rollout-shards \
  --config-path "$CONFIG_PATH" \
  --rows-per-shard 1 \
  --output-manifest "$SHARD_MANIFEST"

sbatch "$ARIA_DSS/data/staging/rollouts/rollout_generation_${RUN_ID}.sbatch"

uv run nbv-status-rollout-shards \
  --shard-manifest "$SHARD_MANIFEST" \
  --final-root "$ARIA_DSS/data/staging/rollouts/$RUN_ID/shards" \
  --output-json "$ARIA_DSS/data/staging/rollouts/$RUN_ID/manifests/status.json" \
  --require-complete
```

For retries, derive the retry set from `nbv-status-rollout-shards`, not from a
recursive DSS scan. A final shard directory is reusable only when validation
passes and both `_owner.json` and `_SUCCESS.json` are present. If a final shard
path exists without a valid success marker, move or remove it only after
operator review; never overwrite a partial final path in place. If a temp shard
path still exists, confirm that no active job owns it before removing it.
