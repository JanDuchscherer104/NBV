---
name: dataset-cache-ops
description: Operate dataset caches reproducibly.
metadata:
  mode: maintenance
  not_when:
    - "package code changes a data or storage contract"
    - "LRZ execution or Rerun visualization is the primary task"
  handoff_to:
    - "lrz-ai-systems for LRZ storage or jobs"
    - "rerun-nbv-inspector for visual inspection"
    - "nearest package owner for data or storage contract changes"
  evidence_required:
    - "resolved owner, config, release, root, split, and artifact version"
    - "reader or smoke output with exact failure context"
  applies_to:
    - "aria_nbv/aria_nbv/data_handling/**"
    - "aria_nbv/tests/data_handling/**"
    - ".configs/**"
    - "docs/contents/setup.qmd"
  triggers:
    - "download or rebuild a dataset cache"
    - "inspect a manifest, split, shard, or immutable store"
  must_read:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
  canonical_sources:
    - "aria_nbv/aria_nbv/data_handling/AGENTS.md"
    - "aria_nbv/aria_nbv/data_handling/README.md"
    - "docs/contents/setup.qmd"
  verification:
    - "owning reader, CLI smoke, or targeted data-handling test"
---

# Dataset Cache Operations

Use this skill for the reproducible operator loop, not for defining dataset or
storage semantics.

1. Read the nearest package owner and resolve the config, release, data root,
   split, shard, and expected artifact version.
2. Use the owning downloader, writer, reader, or CLI. Preserve command,
   provenance, checksums, and partial-failure evidence.
3. Never hand-edit generated manifests, indexes, shards, or payloads. Rebuild
   immutable artifacts when their owner requires it.
4. Run the narrow reader/smoke path and report counts, storage use, version,
   and exact blockers.

Stop when the artifact is reproducibly identified and readable, or when the
owner-backed error and rebuild requirement are explicit.
