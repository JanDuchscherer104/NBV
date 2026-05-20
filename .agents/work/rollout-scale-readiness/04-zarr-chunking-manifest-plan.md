# Plan: Zarr Chunking And Manifest Streamlining

Backlog: `refactor-021`, linked to `issue-032`, `issue-018`, and `issue-022`.

## Problem

The schema-1.0 structural probe showed candidate factual arrays creating many
small chunks and files. In particular, pose arrays with shape `[num_candidates,
width]` used one row per chunk, yielding hundreds of chunk files and megabytes
of overhead for a few tens of kilobytes of raw pose data.

Optional empty audit groups and repeated resolved config trees also add noise.
This is acceptable for tiny debugging stores but not for LRZ-scale generation.

## Desired Contract

Storage should stay factual and auditable while avoiding row-per-candidate
overhead:

- Candidate factual arrays use row-block or byte-budget chunks.
- `q_h/` keeps its own access-pattern-specific chunking.
- selected-depth keeps image-oriented chunking.
- Optional zero-row audit groups have negligible footprint.
- Shard manifests keep enough lineage locally while avoiding repeated large
  resolved config payloads when a campaign-level manifest can own them.

## Implementation Plan

1. Inventory current `_default_chunks` users and classify arrays by access
   pattern:
   - factual row tables,
   - dense `q_h/` state-action views,
   - selected-depth image blocks,
   - optional audit payloads.
2. Replace one-row chunks for 2D factual row tables with a configurable row
   block or approximate byte-budget policy.
3. Preserve custom chunking for `q_h/` and selected-depth arrays.
4. Minimize zero-row optional audit groups by storing only required attrs or
   compact zero-length arrays needed by readers.
5. Split manifest payload into:
   - required per-shard lineage: schema, command, seed, split hash, source
     store ids, config hash, effective retention profile;
   - optional full resolved config: campaign/root manifest or audit-heavy mode.
6. Measure `du`, file count, validation time, and representative read speed
   before/after on the same small probe.

## Tests And Verification

- `cd aria_nbv && uv run pytest tests/rollouts/test_zarr_store.py tests/rollouts/test_dataset_writer.py -q`
- `find <store>.zarr/candidates/pose_world_cam -type f | wc -l`
- `du -sh <store>.zarr <store>.zarr/candidates/* | sort -h`
- Read a candidate minibatch and q_h view after writing to confirm access still
  works.

## Open Decisions For Review

1. Should chunk sizing be row-count based or byte-budget based? Recommended:
   byte-budget internally with a row-count floor/ceiling, because array widths
   differ.
2. What is the first target uncompressed chunk size? Recommended: aim near the
   Zarr guidance of roughly megabyte-scale chunks for scan/minibatch arrays, but
   allow smaller chunks for tiny smoke stores.
3. Should full resolved configs live in every shard? Recommended: keep hashes
   and effective summary in every shard; put full resolved config in campaign
   metadata unless running an audit-heavy standalone shard.
4. Can zero-row optional groups be omitted entirely? Recommended: omit payload
   arrays when disabled only if readers/validators can distinguish disabled from
   corrupt; otherwise keep a tiny marker group.

