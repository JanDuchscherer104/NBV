# Graphify Contract

Graphify is a source-derived navigation index, never an authority. Exact code,
active Typst sources, bibliography entries, and external papers own claims.

The repository pins `graphifyy==0.9.26` and upstream tag commit
`66d8110a534b52df3d660b5fda5aa5461a6b667a`. `.graphify.toml` is the compact
pin and three-partition admission config. The adapter
materializes a temporary corpus, selects literature through
`docs/literature/sources.jsonl`, and converts only explicit Typst, TeX, and Bib
structure into Python-shaped input for the upstream AST. Direct root
`graphify update .` is therefore not canonical.

Native Graphify owns the graph schema, query/path/explain/affected/tree, and
clustering. Graph JSON, reports, HTML, and wiki exports are generated local
state and remain ignored. Rewritten nodes and links retain authoritative source
paths and line locators.

Run `python scripts/graphify_adapter.py sync` or `make graphify-refresh` to
synchronize all partitions. The post-commit hook invokes the same adapter for
config, adapter, bridge, or adapter-classified source changes.

After `python scripts/graphify_adapter.py check` succeeds, use the pinned native
CLI directly. If navigation is insufficient, inspect exact tracked owners with
targeted `rg` and narrow reads; the repository does not maintain query wrappers.

The local manifest records selected source and adapter digests. Freshness is a
content check, so ordinary commits, merges, rebases, and linked worktrees need no
generated companion commit.
