---
name: zarr-python
description: Use when ARIA-NBV work changes Zarr-Python API usage, chunking, codecs, stores, sharding, concurrency, or v2/v3 migration behavior in offline or rollout storage.
metadata:
  mode: implementation
  not_when:
    - "ASE download, ATEK shard, manifest, split, or data smoke work with no Zarr API or storage-layout change"
    - "rollout reward, target, invalidity, or Q_H semantics with no Zarr API or storage-layout change"
    - "model training or scoring changes that only read an existing store"
  handoff_to:
    - "dataset-cache-ops for ASE, ATEK, VIN offline store operation, manifests, splits, smoke checks, or rebuild decisions"
    - "counterfactual-rollout-planner for rollout reward, target, invalidity, or Q_H semantics"
    - "diagnose-aria for concrete Zarr tracebacks, stale stores, or failed validation commands"
    - "lrz-ai-systems for Slurm, DSS, remote filesystem, or container execution constraints"
  evidence_required:
    - "local owner file and symbol for the touched offline or rollout Zarr path"
    - "official Zarr-Python or Context7 evidence for nontrivial API, codec, store, sharding, or migration behavior"
    - "round-trip validation or explicit blocker for changed arrays, chunks, codecs, stores, or readers"
  applies_to:
    - "aria_nbv/aria_nbv/data_handling/**"
    - "aria_nbv/aria_nbv/rollouts/**"
    - "aria_nbv/tests/data_handling/**"
    - "aria_nbv/tests/rollouts/**"
    - ".configs/**"
  triggers:
    - "Zarr"
    - "zarr-python"
    - "create_array"
    - "LocalStore"
    - "FsspecStore"
    - "chunking"
    - "codec"
    - "compressor"
    - "sharding"
    - "Zarr v3"
  must_read:
    - "aria_nbv/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "aria_nbv/aria_nbv/rollouts/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/README.md"
  canonical_sources:
    - "aria_nbv/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "aria_nbv/aria_nbv/rollouts/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/README.md"
    - "aria_nbv/pyproject.toml"
  context7_refs:
    - "/zarr-developers/zarr-python"
  tool_refs:
    - "mcp__MCP_DOCKER.get_library_docs"
    - "mcp__MCP_DOCKER.resolve_library_id"
    - "mcp__code_index.search_code_advanced"
  verification:
    - "make scaffold-audit for skill guidance changes"
    - "cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py tests/rollouts/test_zarr_store.py for storage behavior changes"
    - "cd aria_nbv && uv run nbv-rollouts-info --store ../.data/offline_cache/rollouts_v1_smoke.zarr --validate when rollout stores are touched"
---

# Zarr Python

Use this skill when ARIA-NBV work changes Zarr-Python usage rather than merely
operating an existing dataset or rollout artifact.

## When To Use

- Zarr-Python 3 API changes such as `create_array`, `open_group`, `LocalStore`,
  `FsspecStore`, codec imports, or group/array creation behavior.
- Chunk shape, sharding, compression, selected-depth storage, or high-throughput
  rollout reader/writer changes.
- Zarr v2/v3 migration, metadata layout, cloud/object-store access, or
  concurrency assumptions that affect ARIA storage code.

## Read First

1. `aria_nbv/AGENTS.md`
2. `aria_nbv/aria_nbv/data_handling/AGENTS.md`
3. `aria_nbv/aria_nbv/rollouts/AGENTS.md`
4. The implementation file being changed.
5. Context7 or official Zarr-Python docs for nontrivial API behavior.

## Rules

- Treat `aria_nbv/pyproject.toml` as the local dependency source; do not copy
  upstream community install or Python-version claims into ARIA guidance.
- Keep VIN offline numeric blocks under `aria_nbv.data_handling`; keep rollout
  replay and `q_h` Zarr artifacts under `aria_nbv.rollouts`.
- Do not mutate VIN offline stores to carry rollout replay data.
- Do not hand-edit Zarr arrays, manifests, sample indexes, or split arrays to
  silence validation; fix the writer, reader, or generator.
- Prefer existing helpers such as `VinOfflineShardWriter`,
  `VinOfflineStoreReader`, `write_rollout_zarr_store`, and
  `validate_rollout_zarr_store` before adding new storage code.
- For chunking, codec, sharding, `LocalStore`, `FsspecStore`, concurrency, or
  migration behavior, confirm current Zarr-Python docs before implementation.

## Workflow

1. Identify whether the owner is data handling, rollouts, or an adjacent skill.
2. Localize the existing writer/reader/helper with `rg` or code-index evidence.
3. Check official Zarr-Python guidance when API behavior is not trivial.
4. Change the smallest owner surface and keep ARIA storage responsibilities
   separate.
5. Prove the changed path with round-trip tests, validation CLIs, or an explicit
   blocker.

## Verification

- Guidance-only edits: `make scaffold-audit` and `make check-agent-memory`.
- Offline-store behavior: `cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py tests/data_handling/test_public_api_contract.py`.
- Rollout Zarr behavior: `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_info_cli.py`.
- CLI smoke when rollout stores are touched: `cd aria_nbv && uv run nbv-rollouts-info --store ../.data/offline_cache/rollouts_v1_smoke.zarr --validate`.
