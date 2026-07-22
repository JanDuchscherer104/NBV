---
name: dataset-cache-ops
description: Use for ARIA-NBV ASE/ATEK data, meshes, immutable VIN stores, versions, splits, storage estimates, and smoke checks.
metadata:
  mode: maintenance
  not_when:
    - "training or scoring only consumes an existing valid store"
    - "Rerun display behavior is the only affected surface"
    - "Zarr library API behavior changes rather than store operation"
  handoff_to:
    - "rerun-nbv-inspector for visual inspection of compatible samples"
    - "lrz-ai-systems for LRZ storage, Slurm, or container execution"
    - "agents-db for durable data debt or blocked-store records"
    - "external Zarr documentation capability for library API changes"
  evidence_required:
    - "exact config, data root, manifest, split, and shard identity"
    - "strict reader or smoke result with version and failure reason"
    - "storage estimate and immutable rebuild decision when relevant"
  applies_to:
    - "aria_nbv/aria_nbv/data_handling/**"
    - ".configs/**"
    - "docs/contents/setup.qmd"
  triggers:
    - "ASE or ATEK dataset operation"
    - "immutable offline store"
    - "data smoke or split manifest"
    - "storage estimate"
  must_read:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/README.md"
  canonical_sources:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/README.md"
    - "docs/contents/setup.qmd"
    - "aria_nbv/pyproject.toml"
  context7_refs:
    - "/pydantic/pydantic"
    - "/jcrist/msgspec"
    - "/zarr-developers/zarr-python"
    - "/facebookresearch/atek"
    - "/facebookresearch/efm3d"
  literature_refs:
    - "docs/contents/literature/project_aria.qmd"
    - "ProjectAria-ASE-2025"
    - "EFM3D-straub2024"
  tool_refs:
    - "mcp__code_index.search_code_advanced"
    - "mcp__MCP_DOCKER.get_library_docs"
  verification:
    - "cd aria_nbv && uv run pytest tests/data_handling/test_vin_offline_store.py"
    - "make check-agent-memory for data guidance changes"
---

# Dataset And Cache Operations

1. Resolve the owning config, dataset release, source root, split, and expected
   immutable store version.
2. Inspect manifests and sample indexes through the owning reader or CLI; never
   hand-edit derived artifacts to pass validation.
3. Download or rebuild into the configured data root, preserving source URLs,
   shard identity, checksums, and partial-download evidence.
4. Run the narrow smoke or strict-reader check and report usable/invalid counts,
   storage consumed, and any exact version blocker.

VIN stores are rebuild-only immutable artifacts. Zarr API, codec, chunk,
sharding, or concurrency changes belong to the package writer/reader contract
and require official library evidence plus round-trip tests.

Complete when the artifact is reproducibly identified, strictly readable or
explicitly blocked, and no derived manifest or payload was edited by hand.
