# Graphify Contract

Graphify is a source-derived navigation index, never an authority. Exact code,
active Typst sources, bibliography entries, and external papers own claims.

The repository pins `graphifyy==0.9.22` and upstream capability commit
`abff1b1ca4052fcf9d955c5f6a034088723f4536`. `.graphify.toml` is the sole compact
pin, activation-history, and three-partition admission config. The adapter
materializes a temporary corpus, selects literature through
`docs/literature/sources.jsonl`, and converts only explicit Typst, TeX, and Bib
structure into Python-shaped input for the upstream AST. Direct root
`graphify update .` is therefore not canonical.

Native Graphify owns the graph schema, `GRAPH_REPORT.md`, query/path/explain/tree,
clustering, and merge driver. HTML is generated on demand and remains ignored;
no wiki is maintained. Canonical nodes and links retain exact authoritative
source paths and line locators through the adapter.

Run `python scripts/graphify_adapter.py sync` or `make graphify-refresh` to
synchronize all partitions, and use `sync --check` for deterministic diff
validation. The post-commit hook synchronously invokes the same adapter for
config, adapter, bridge, or adapter-classified source changes.

After `python scripts/graphify_adapter.py check` succeeds, use the pinned native
CLI directly. If navigation is insufficient, inspect exact tracked owners with
targeted `rg` and narrow reads; the repository does not maintain query wrappers.

Authoring history uses `S -> G`: a corpus-changing source commit is followed
immediately by a graph-only commit that records the source tree digest. Mixed
authoring commits and delayed catch-up graph commits fail. CI checks adjacency
after the immutable activation commit recorded in `.graphify.toml`. Merge or
squash products are validated from their final tree digest and deterministic
no-diff regeneration.
