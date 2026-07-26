# Graphify query, path, and explain

Use the pinned upstream Graphify public CLI only after the repository freshness
check succeeds:

```bash
make graphify-freshness
graphify query "<question>"
graphify path "<source>" "<target>"
graphify explain "<node>"
```

`query` uses BFS by default. Add `--dfs` for a dependency chain and `--budget N`
to bound output. Select a small set of terms that occur in node labels in
`graphify-out/graph.json`; upstream matching is literal, so vocabulary alignment
avoids empty or noisy traversals.

Treat Graphify output as navigation evidence, not authority. Cite its
`source_location` when useful, then verify important claims in the owning code,
tests, configuration, or documentation.

If freshness fails, the CLI is unavailable, no matching node exists, or
traversal lacks enough evidence, do not emulate Graphify locally. Follow
`.agents/references/source_order.md` and inspect exact source owners with
targeted `rg` plus narrow file reads. State that fallback explicitly.
