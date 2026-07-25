# Graphify Contract

Graphify is a source-derived navigation index, never an authority. Exact code,
tests, configs, guidance, thesis sources, and literature sources own claims.

The repository pins `graphifyy==0.9.22` and upstream capability commit
`abff1b1ca4052fcf9d955c5f6a034088723f4536`. `.graphify.toml` owns the four
first-match partitions (`literature`, `scaffold`, `thesis`, `code`), role tags,
schema version, and canonical artifact allowlist. `.graphifyignore` is the
matching upstream extraction boundary.

Only `graphify-out/graph.json`, `manifest.json`, and `GRAPH_REPORT.md` are
tracked. HTML, wiki output, caches, interpreter pointers, query memory,
reflections, logs, and temporary extraction state remain ignored. Canonical
edges distinguish `EXTRACTED`, `INFERRED`, and `AMBIGUOUS` origin from numeric
confidence and carry exact source digests and locators. Inferred edges survive
structural refresh only while every source digest still matches.

`python3 scripts/graphify_refresh.py --mode structural` refreshes code without
semantic extraction. `--mode sync` explicitly refreshes source-reference
partitions. Neither mode calls an LLM. The post-commit hook dispatches the
structural mode asynchronously for code and leaves semantic partitions stale
for explicit sync.

After `python3 scripts/check_graphify_freshness.py --quiet` succeeds, use the
pinned upstream public CLI directly: `graphify query`, `graphify path`, and
`graphify explain`. If freshness fails or navigation is insufficient, inspect
exact tracked source owners with targeted `rg` and narrow reads; the repository
does not maintain a second query implementation.

Authoring history uses `S -> G`: a corpus-changing source commit is followed
immediately by a graph-only commit that records the source tree digest. Mixed
authoring commits and delayed catch-up graph commits fail. CI checks adjacency
after the immutable activation commit recorded in `.graphify.toml`. Merge or
squash products are validated from their final tree digest and deterministic
no-diff regeneration.
