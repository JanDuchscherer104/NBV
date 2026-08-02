# ARIA Graphify Boundary

Read this only before a Graphify build, refresh, or semantic reconciliation.
Graphify is trusted navigation; exact repository owners remain authoritative.

## Freshness And Corpus

- `make graphify-state-check` is the strict scaffold and pre-push gate;
  `make graphify-usable-check` validates ordinary navigation.
- A Git HEAD mismatch alone is not stale when recorded revisions are ancestors
  and indexed bytes match.
- ARIA owns `.graphifyignore`, the freshness checker, and the ignored Markdown
  projection. Build that projection with `python3
  scripts/build_graphify_projection.py --output graphify-input --aria-code-ref
  "$(git rev-parse HEAD)"`, then use the repository root as the corpus root.

## Upstream Lifecycle

- Keep `.agents/skills/graphify` byte-identical to upstream. Use upstream
  dispatch, cache, merge, manifest, and reconciliation behavior.
- Prefer an upstream-supported CLI backend. A Codex-native semantic run uses a
  self-contained prompt with `fork_turns="none"`.
- Accept a refresh only after every dispatched file is accounted for and
  existing-file nodes outside that set are excluded. Until then, keep the last
  valid graph queryable, leave the strict gate stale, and verify affected source
  locations directly.

## Marker And Worktrees

- Graphify 0.9.31 writes `graphify-out/needs_update`. Remove
  `graphify-out/needs_update` only after refresh, coverage, and reconciliation
  pass; leave it after partial, failed, or unverified work.
- Run `scripts/setup_worktree_env.sh` in linked worktrees. Only the
  content-addressed `semantic` and `semantic-deep` caches are shared; projection,
  graph, manifest, AST, and run state stay worktree-local.
