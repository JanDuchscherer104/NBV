# ARIA-NBV KG Profile

`.configs/infrastructure/litkg.toml` is the operator entrypoint for ARIA-NBV knowledge-graph ingestion.

Default runtime representation:

- Graphify-style Markdown/JSON under `.agents/kg/generated/literature` is the
  primary local output.
- Neo4j export bundles under `.agents/kg/generated/neo4j-export` are the
  default graph-traversal output.
- CodeGraphContext indexes `aria_nbv/aria_nbv` into the local Neo4j runtime for symbol-level Python graph queries.
- Graphiti is optional for temporal doc/memory ingestion and is disabled by default in the TOML profile.
- MemPalace remains separate through `make memory-mine`; use it for repo memory retrieval, not as the structural literature/code KG backend.

Role boundary:

| Surface | Role |
| --- | --- |
| litkg-rs | Structural project KG, source routing, retrieval, and consolidation proposal layer. |
| graphify/JSONL | Durable local KG artifact format rebuilt from source files. |
| Neo4j | Optional traversal/runtime database over exported bundles. |
| Graphiti | Optional temporal runtime ingestion for docs or memory episodes. |
| MemPalace | Separate episodic memory-mining backend invoked by `make memory-mine`. |
| `.agents/kg/generated/**` | Internal generated artifacts; do not add raw KG output to public Quarto navigation. |

Useful commands:

```bash
make kg-capabilities
make kg-search KG_QUERY="entity-aware RRI"
make kg-brief KG_TOPIC="VIN offline-store diagnostics"
make kg-route KG_TASK="debug candidate pose frame mismatch"
make kg-show-paper KG_PAPER="VIN-NBV-frahm2025"
make kg-sync
make kg-materialize
make kg-semantic-enrich
make kg-export-neo4j
make kg-index-code
make kg-ingest-docs
make kg-ingest-papers
make kg-refresh-light
make kg-refresh-code
make kg-refresh-lit
make kg-refresh-full
```

Generated KG output is ignored by Git. Rebuild it from `.configs/infrastructure/litkg.toml`
and the source bibliography/docs when needed; commit only source config,
curated docs, or an explicit artifact snapshot.
