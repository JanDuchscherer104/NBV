---
id: 2026-07-13_g007_data_hierarchy_and_root_contract
date: 2026-07-13
title: "G007 Data Hierarchy And Root Contract"
status: done
topics: [data-handling, raw-data, public-api, simplification]
confidence: high
canonical_updates_needed: []
---

# G007 Data Hierarchy And Root Contract

## Scope

Completed the raw/offline hierarchy transition without changing raw dataset,
immutable-store, identifier, CLI, or persisted-schema behavior.

## Changes

- Moved typed EFM payloads from `data_handling.efm_views` to
  `data_handling.raw.views`.
- Split shared ASE-ATEK identifier conversion into
  `data_handling.identifiers` and folded dataset-private shard resolution and
  semidense-bound helpers into `data_handling.raw.dataset`.
- Deleted the unused `_looks_like_sample_key` helper and both obsolete module
  paths without compatibility modules.
- Contracted `data_handling.__all__` from 47 names to the approved eight-name
  stable interface; specialized callers now import owner leaves.

Production Python LOC decreased from 67,944 to 67,829 (-115). The Python
module count is unchanged.

## Verification

- Ruff format/check, compileall, the static typing contract, exact root-export
  assertions, CLI help, stale-import scans, and Graphify refresh passed.
- AST parity proved 16 moved utility definitions and 15 moved view definitions
  unchanged; only the zero-caller predicate was deleted.
- The broad data/raw/pose/Lightning/Rerun run produced 181 passes and 6 skips;
  its sole checkout-local missing-mesh failure passed when both shared ASE
  shards and meshes were attached. An additional 105 Lightning, VIN, and app
  tests passed.
- Quartodoc navigation and generated glossary references now use the owning
  leaf paths.
- `make check-agent-memory` remains blocked by the branch baseline's tracked
  `.omx` runtime artifacts; the failure does not reference this debrief or any
  G007-owned path.

## Canonical Updates Needed

- None. The package guidance, READMEs, API navigation, and glossary source now
  describe the active hierarchy.
