---
name: dataset-cache-ops
description: Use when operating or documenting ARIA-NBV ASE downloads, ATEK shards, meshes, immutable VIN offline stores, dataset-version updates, split manifests, storage estimates, and data smoke checks.
metadata:
  mode: maintenance
  not_when:
    - "model training or scoring changes that only consume an existing store"
    - "Rerun display issues with a valid store and no data-contract change"
    - "legacy cache revival or migration unless explicitly requested"
  handoff_to:
    - "diagnose-aria for concrete data smoke failures or tracebacks"
    - "rerun-nbv-inspector for visual inspection of compatible offline samples"
    - "zarr-python for Zarr API, chunk, codec, store, sharding, concurrency, or migration changes"
    - "lrz-ai-systems for remote storage, Slurm, DSS, or container execution"
    - "agents-db for durable data debt or blocked-store records"
  evidence_required:
    - "manifest, sample-index, split, and shard validation summary"
    - "exact config path, data root, and smoke command for the store"
    - "strict reader result or explicit version/blocker reason"
  applies_to:
    - "aria_nbv/aria_nbv/data_handling/**"
    - ".configs/**"
    - "docs/contents/setup.qmd"
    - "docs/reference/**"
  triggers:
    - "ASE download"
    - "ATEK shard"
    - "offline store"
    - "data smoke"
  must_read:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - ".agents/memory/state/GOTCHAS.md"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
  canonical_sources:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "docs/contents/setup.qmd"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - ".agents/memory/state/GOTCHAS.md"
  context7_refs:
    - "/pydantic/pydantic"
    - "/jcrist/msgspec"
    - "/zarr-developers/zarr-python"
    - "/facebookresearch/atek"
    - "/facebookresearch/efm3d"
  literature_refs:
    - "egocentric-aria-substrate"
    - "ProjectAria-ASE-2025"
    - "EFM3D-straub2024"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.get_library_docs"
  verification:
    - "cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py"
    - "make check-agent-memory for dataset guidance changes"
---

# Dataset Cache Ops

## OMX Integration

OMX may schedule data work, but this skill owns ARIA dataset and immutable-store
evidence. Feed OMX exact store health, smoke commands, and rebuild/migration
constraints; do not make runtime orchestration or remote execution decisions
inside this skill.

## When To Use

Use this skill for:

- ASE downloader and data-root setup
- ATEK shards, mesh availability, and snippet coverage checks
- immutable VIN offline stores, manifests, split files, and storage estimates
- dataset-format/version updates for local immutable VIN offline stores
- `offline_only.toml`, VIN diagnostics, and data smoke commands

Do not use it to restore legacy cache migration or removed training APIs.
Hand off to `zarr-python` when the task changes Zarr API usage, chunking,
codecs, stores, sharding, concurrency, or migration behavior rather than only
operating or validating an existing ARIA store.

## Read First

1. `aria_nbv/AGENTS.md`
2. `aria_nbv/aria_nbv/data_handling/AGENTS.md`
3. `README.md`
4. `aria_nbv/aria_nbv/data_handling/AGENTS.md`
5. `.agents/memory/state/GOTCHAS.md`

## Rules

- The canonical training path is `VinOfflineDataset` configured through
  `VinOfflineSourceConfig` with `kind = "offline"`.
- Rebuild available immutable stores with `VinOfflineWriter`; do not revive
  removed legacy cache datasets, providers, or migration tools.
- Keep split manifests and sample indexes file-backed and inspectable.
- Prefer list/smoke commands before expensive downloads or builds.
- Record exact failing commands and traceback summaries when data checks fail.
- For immutable-store checks, validate `manifest.json`, `sample_index.jsonl`,
  split `.npy` files, block presence, tensor shapes, dtypes, and numeric byte
  estimates on a tiny fixture before running large stores.
- Use `collect_vin_offline_dataset_stats` and the VIN Offline Dataset panel for
  diagnostics rather than legacy cache inspection helpers.

## Dataset Version Updates

Use this workflow when `OFFLINE_DATASET_VERSION` changes or a local store must be
updated to the current reader contract.

- Keep runtime readers strict. Do not add `allow_legacy`, accepted-version
  lists, old-cache imports, or permanent migration helpers just to read an old
  store.
- Prefer a clean `VinOfflineWriter` rebuild for canonical stores. Use an
  artifact migration only when the user explicitly wants to preserve expensive
  existing payloads and you have verified that old shard arrays still satisfy
  the current reader semantics.
- Before any artifact mutation, read-only validate: manifest version, row
  counts, shard count, split counts, unique `sample_key`s, required block names,
  tensor shapes/dtypes, and optional block flags. Record the exact command and
  summary in the debrief.
- Save as much as intended, not blindly. If a version bump only adds optional
  manifest fields or optional blocks, a manifest-only migration may be valid. If
  block layout, tensor semantics, frame conventions, candidate ordering, or RRI
  meaning changed, rebuild affected rows instead of pretending old data is new.
- Avoid recomputing expensive payloads unnecessarily. For small additions,
  build a sidecar store with the current writer for only the new snippets/rows,
  then merge by copying whole new shards and updating manifest/index/splits.
  Disable new optional blocks in the sidecar unless the existing store is also
  being deliberately backfilled.
- Mutate store metadata atomically: write `*.tmp`, then `os.replace`; update
  `manifest.json`, `sample_index.jsonl`, and split `.npy` files consistently.
  Never hand-edit shard arrays or msgpack payloads to silence validation.
- Put one-off migration/merge scripts and temporary TOML under `/tmp` or another
  untracked scratch path. Delete all temporary scripts, sidecar stores, and
  migration helpers after verification; do not commit migration logic unless it
  becomes a supported repeatable tool.
- After the update, prove the strict reader opens the store, old-version
  rejection tests still pass, no legacy compatibility flags were introduced,
  and the original smoke command succeeds.

## Verification

- `cd aria_nbv && uv run nbv-downloader -m list`
- `cd aria_nbv && uv run nbv-summary --config-path ../.configs/training/vin/offline_only.toml`
- `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py tests/data_handling/test_public_api_contract.py`
- `cd aria_nbv && uv run pytest tests/vin/test_vin_utils.py`
- `rg -n "allow_legacy|accepted_versions|legacy.*version|v5" aria_nbv/aria_nbv/data_handling aria_nbv/tests/data_handling`
